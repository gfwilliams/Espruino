#!/usr/bin/python3

# This file is part of Espruino, a JavaScript interpreter for Microcontrollers
#
# Copyright (C) 2013 Gordon Williams <gw@pur3.co.uk>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# ----------------------------------------------------------------------------------------
# Scans files for comments of the form /*JSON......*/ and then builds a tree structure of ifs to
# efficiently detect the symbols without using RAM. See common.py for formatting
# ----------------------------------------------------------------------------------------

import subprocess;
import re;
import json;
import sys;
import os;
scriptdir = os.path.dirname(os.path.realpath(__file__))
basedir = scriptdir+"/../"
sys.path.append(basedir+"scripts");
sys.path.append(basedir+"boards");
import importlib;
import common;
from inspect import currentframe, getframeinfo
from collections import OrderedDict;

if len(sys.argv)<2 or sys.argv[len(sys.argv)-2][:2]!="-B" or sys.argv[len(sys.argv)-1][:2]!="-F":
	print("USAGE: build_jswrapper.py ... -BBOARD -Fwrapperfile.c modulename:path/to/modulesource.js")
	print("")
	print("           -Fwrapperfile.c                     ; include a jswrap file in the build ")
	print("")
	print("           path/to/modulename.js               ; include a JS module called modulename")
	print("           modulename:path/to/modulesource.js  ; include a JS module called modulename")
	print("           _:bootcode                          ; JS code to be executed at boot time")
	print("             ; These can be specified in the JSMODULESOURCES environment variable")
	exit(1)

boardName = sys.argv[len(sys.argv)-2]
boardName = boardName[2:]

wrapperFileName = sys.argv[len(sys.argv)-1]
wrapperFileName = wrapperFileName[2:]

# Load any JS modules specified on command-line
jsmodules = {}     # JS modules to be included
jsbootcode = False # if set, JS code to be run at boot time
for i in range(1,len(sys.argv)):
  arg = sys.argv[i]
  if arg[0]!="-" and arg[-3:]==".js":
    if arg.find(":")>=0:
      colon = arg.find(":")
      modulename = arg[:colon]
      arg = arg[colon+1:]
    else:
      modulename = arg.rsplit('/',1)[1][:-3]
      if modulename[-4:]==".min": modulename=modulename[:-4]
    print("Loading JS module: "+arg+" -> "+modulename)
    jscode = open(arg, "r").read()
    if modulename=="_":
      jsbootcode = jscode
    else:
      jsmodules[modulename] = jscode

# List of argument specifiers (JSWAT...) that have been used
argSpecs = []
# for each argument specifier, the code required
argSpecCalls = []

# ------------------------------------------------------------------------------------------------------

def codeOut(s):
#  print str(s)
  wrapperFile.write(s+"\n");

def FATAL_ERROR(s):
  sys.stderr.write("ERROR: "+s)
  exit(1)

# ------------------------------------------------------------------------------------------------------

def getConstructorTestFor(className, variableName):
    # IMPORTANT - we expect built-in objects to be native functions with a pointer to
    # their constructor function inside
    for jsondata in jsondatas:
      if jsondata["type"]=="constructor" and jsondata["name"]==className:
        if variableName=="constructorPtr": # jsvIsNativeFunction/etc has already been done
          return "constructorPtr==(void*)"+jsondata["generate"];
        else:
          return "jsvIsNativeFunction("+variableName+") && (void*)"+variableName+"->varData.native.ptr==(void*)"+jsondata["generate"];
    print("No constructor found for "+className)
    exit(1)

def getTestFor(className, static):
  if static:
    return getConstructorTestFor(className, "parent");
  else:
    if className=="String": return "jsvIsString(parent)"
    if className=="Pin": return "jsvIsPin(parent)"
    if className=="Integer": return "jsvIsInt(parent)"
    if className=="Double": return "jsvIsFloat(parent)"
    if className=="Number": return "jsvIsNumeric(parent)"
    if className=="Object": return "parent" # we assume all are objects
    if className=="Array": return "jsvIsArray(parent)"
    if className=="ArrayBuffer": return "jsvIsArrayBuffer(parent) && parent->varData.arraybuffer.type==ARRAYBUFFERVIEW_ARRAYBUFFER"
    if className=="ArrayBufferView": return "jsvIsArrayBuffer(parent) && parent->varData.arraybuffer.type!=ARRAYBUFFERVIEW_ARRAYBUFFER"
    if className=="Function": return "jsvIsFunction(parent)"
    return getConstructorTestFor(className, "constructorPtr");

# Dump the current position in this file
def getCurrentFilePos():
  cf = currentframe()
  return "build_jswrapper.py:"+str(cf.f_back.f_lineno)

def toArgumentType(argName):
  if argName=="": return "JSWAT_VOID";
  if argName=="JsVar": return "JSWAT_JSVAR";
  if argName=="JsVarArray": return "JSWAT_ARGUMENT_ARRAY";
  if argName=="bool": return "JSWAT_BOOL";
  if argName=="pin": return "JSWAT_PIN";
  if argName=="int32": return "JSWAT_INT32";
  if argName=="int": return "JSWAT_INT32";
  if argName=="float": return "JSWAT_JSVARFLOAT";
  FATAL_ERROR("toArgumentType: Unknown argument name "+argName+"\n")

def toCType(argName):
  if argName=="": return "void";
  if argName=="JsVar": return "JsVar*";
  if argName=="JsVarArray": return "JsVar*";
  if argName=="bool": return "bool";
  if argName=="pin": return "Pin";
  if argName=="int32": return "int";
  if argName=="int": return "JsVarInt";
  if argName=="float": return "JsVarFloat";
  FATAL_ERROR("toCType: Unknown argument name "+argName+"\n")

def toCBox(argName):
  if argName=="JsVar": return "";
  if argName=="bool": return "jsvNewFromBool";
  if argName=="pin": return "jsvNewFromPin";
  if argName=="int32": return "jsvNewFromInteger";
  if argName=="int": return "jsvNewFromInteger";
  if argName=="float": return "jsvNewFromFloat";
  FATAL_ERROR("toCBox: Unknown argument name "+argName+"\n")

def toCUnbox(argName):
  if argName=="JsVar": return "";
  if argName=="bool": return "jsvGetBool";
  if argName=="pin": return "jshGetPinFromVar";
  if argName=="int32": return "jsvGetInteger";
  if argName=="int": return "jsvGetInteger";
  if argName=="float": return "jsvGetFloat";
  FATAL_ERROR("toCUnbox: Unknown argument name "+argName+"\n")


def hasThis(func):
  return func["type"]=="property" or func["type"]=="method" or func.get("thisParam")

def getParams(func):
  params = []
  if "params" in func:
    for param in func["params"]:
      params.append(param)
  return params

def getResult(func):
  result = [ "", "Description" ]
  if "return" in func: result = func["return"]
  return result

def getArgumentSpecifier(jsondata):
  if ("generate" in jsondata) and (jsondata["generate"].startswith("jswSymbolIndex_")):
    return "JSWAT_SYMBOL_TABLE" # we should just use the value here to create a NativeObject from the symbol table
  params = getParams(jsondata)
  result = getResult(jsondata);
  s = [ toArgumentType(result[0]) ]
  if hasThis(jsondata): s.append("JSWAT_THIS_ARG");
  # Either it's a variable/property, in which case we need to execute the native function in order to return the correct info
  if jsondata["type"]=="variable" or common.is_property(jsondata):
    s.append("JSWAT_EXECUTE_IMMEDIATELY")
  # Or it's an object, in which case the native function contains code that creates it - and that must be executed too.
  # It also returns JsVar
  if jsondata["type"]=="object":
    s = [ toArgumentType("JsVar"), "JSWAT_EXECUTE_IMMEDIATELY" ]
  # JSWAT_SYMBOL_TABLE
  n = 1
  for param in params:
    s.append("("+toArgumentType(param[1])+" << (JSWAT_BITS*"+str(n)+"))");
    n=n+1
  if n>5:
    sys.stderr.write(json.dumps(jsondata, sort_keys=True, indent=2)+"\n")
    FATAL_ERROR("getArgumentSpecifier: Too many arguments to fit in type specifier, Use JsVarArray\n")

  argSpec = " | ".join(s);
  return argSpec

def getCDeclaration(jsondata, name):
  # name could be '(*)' for a C function pointer
  params = getParams(jsondata)
  result = getResult(jsondata);
  s = [ ]
  if hasThis(jsondata): s.append("JsVar*");
  for param in params:
    s.append(toCType(param[1]));
  return toCType(result[0])+" "+name+"("+",".join(s)+")";

def codeOutSymbolTable(builtin):
  codeName = builtin["name"]
  # sort by name
  builtin["functions"] = sorted(builtin["functions"], key=lambda n: n["name"]);
  # output tables
  listSymbols = []
  listChars = ""
  strLen = 0
  for sym in builtin["functions"]:
    symName = sym["name"];

    if builtin["name"]=="global" and symName in libraries:
      continue # don't include libraries on global namespace
    if "generate" in sym:
      cast = ""
      if sym["generate"].startswith("jswSymbolIndex_"): cast="(size_t)";
      listSymbols.append("{"+", ".join([str(strLen), getArgumentSpecifier(sym), "(void (*)(void))"+cast+sym["generate"]])+"}")
      listChars = listChars + symName + "\\0";
      strLen = strLen + len(symName) + 1
    else:
      print (codeName + "." + symName+" not included in Symbol Table because no 'generate'")
  builtin["symbolTableChars"] = "\""+listChars+"\"";
  builtin["symbolTableCount"] = str(len(listSymbols));
  builtin["symbolListName"] = "jswSymbols_"+codeName.replace(".prototype", "_prototype");
  if name in constructors:
    builtin["constructorPtr"]="(void (*)(void))"+constructors[name]["generate"]
    builtin["constructorSpec"]=getArgumentSpecifier(constructors[name])
  else:
    builtin["constructorPtr"]="0"
    builtin["constructorSpec"]="0"
  codeOut("static const JswSymPtr "+builtin["symbolListName"]+"[] FLASH_SECT = {\n  "+",\n  ".join(listSymbols)+"\n};");

def codeOutBuiltins(indent, builtin):
  codeOut(indent+"jswBinarySearch(&jswSymbolTables["+builtin["indexName"]+"], parent, name);");

#================== to remove JS-definitions given by blacklist==============
def delete_by_indices(lst, indices):
    indices_as_set = set(indices)
    return [ lst[i] for i in range(len(lst)) if i not in indices_as_set ]

def removeBlacklistForWrapper(blacklistfile,datas):
	json_File = open(blacklistfile,'r')
	blacklist = json.load(json_File)
	toremove = []
	for idx,jsondata in enumerate(datas):
		if "class" in jsondata:
			if "name" in jsondata:
				for black in blacklist:
					if jsondata["class"] == black["class"]:
						if(jsondata["name"] == black["name"] or black["name"] == "*"):
							toremove.append(idx)
							print("Removing "+black["class"]+"."+black["name"]+" due to blacklist wildcard")
# extension by jumjum
		else:
			if "name" in jsondata:
				for black in blacklist:
					if black["class"] == "__":
						if jsondata["name"] == black["name"]:
						  toremove.append(idx)
						  print("Removing global."+black["name"]+" due to blacklist wildcard")
		if "type" in jsondata:
			if "class" in jsondata:
				for black in blacklist:
					if jsondata["class"] == black["class"]:
						if black["name"] == "*":
						  toremove.append(idx)
						  print("Removing "+black["class"]+" due to blacklist wildcard")
			if "instanceof" in jsondata:
				for black in blacklist:
					if jsondata["instanceof"] == black["class"]:
						if black["name"] == "*":
						  toremove.append(idx)
						  print("Removing "+black["class"]+" due to blacklist wildcard")

#  end extension by jumjum
	return delete_by_indices( datas, toremove)
# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------

print("BOARD "+boardName)
board = importlib.import_module(boardName)

jsondatas = common.get_jsondata(is_for_document = False, parseArgs = True, boardObject = board)
if 'BLACKLIST' in os.environ:
	jsondatas = removeBlacklistForWrapper(os.environ['BLACKLIST'],jsondatas)

includes = common.get_includes_from_jsondata(jsondatas)

# work out what we have actually got
classes = {}      # list of class names
constructors = {}
objectChecks = {} # class name -> the check for this class Type

for jsondata in jsondatas:

  if not "type" in jsondata:
    print("ERROR: no type for "+json.dumps(jsondata, sort_keys=True, indent=2))
    exit(1)

  if jsondata["type"] in ["idle","kill","init","include"]: continue

  if not "name" in jsondata:
    print("WARNING: no name for "+json.dumps(jsondata, sort_keys=True, indent=2))

  if jsondata["type"]=="object":
    if "check" in jsondata:
      objectChecks[jsondata["name"]] = jsondata["check"]
    if jsondata["name"] in classes:
      print("ERROR: "+jsondata["name"]+" is defined twice");
      exit(1);
    classes[jsondata["name"]] = jsondata

  if jsondata["type"] in ["function","variable","constructor"]:
    if not "thisParam" in jsondata: jsondata["thisParam"] = False

  if not "instanceOf" in jsondata:
    print("WARNING: No instanceOf for "+jsondata["name"])

  if jsondata["type"]=="constructor":
    if not jsondata["name"] in constructors:
      constructors[jsondata["name"]] = jsondata
    else:
      print("ERROR: duplicate constructor "+jsondata["name"])
      exit(1)

  if jsondata["type"]=="object":
    if "instanceOf" in jsondata:
      jsondatas.append({
        "autogenerated":getCurrentFilePos(),
        "type":"variable",
        "thisParam":False,
        "name":"__proto__",
        "memberOf":jsondata["name"],
        "generate" : "jswSymbolIndex_"+jsondata["instanceOf"].replace(".","_")+"_prototype",
        "return" : ["JsVar"],
        "filename" : jsondata["filename"]
      });
    if not "generate" in jsondata and not "generate_full" in jsondata:
      jsondata["autogenerated"] = getCurrentFilePos()
      jsondata["thisParam"] = False
      jsondata["return"] = ["JsVar"]
      jsondata["generate"] = "jswSymbolIndex_"+jsondata["name"].replace(".","_")

# Add basic classes if we have prototypes for classes, but not the class itself
for className in classes:
  if className[-10:]==".prototype" and not className[:-10] in classes:
    print("Auto-creating class for "+className[:-10]);
    classes[className[:-10]] = {
        "autogenerated":getCurrentFilePos(),
        "type":"object", "name": className[:-10],
        "filename" : classes[className]["filename"],
      };


print("Finding Libraries")
libraries = []
for jsondata in jsondatas:
  if jsondata["type"]=="library":
    print(" - Found library "+jsondata["name"])
    libraries.append(jsondata["name"])

print("Creating Symbol Tables")
symbolTables = {}
# Add main types
for className in classes:
  symbolTables[className] = { "autogenerated":getCurrentFilePos(), "type" : "object", "name" : className, "functions" : [] }
for libName in libraries:
#  if libName in symbolTables:
#    print("ERROR: Name conflict for "+libName+" while adding Library");
#    print("Existing: "+json.dumps(symbolTables[libName], sort_keys=True, indent=2))
#    exit(1);
  # ... we know there will already be a 'class' for the library name...
  symbolTables[libName] = { "autogenerated":getCurrentFilePos(), "type" : "library", "name" : libName, "functions" : [] }

# Now populate with prototypes
for className in classes:
  if className[-10:]==".prototype":
    jsondatas.append({
        "autogenerated":getCurrentFilePos(),
        "type":"variable",
        "thisParam":False,
        "name":"prototype",
        "memberOf":className[:-10],
        "generate" : "jswSymbolIndex_"+className.replace(".","_"),
        "return" : ["JsVar"],
        "filename" : classes[className]["filename"]
    })
    if "memberOf" in classes[className]:
      print("ERROR: Class "+className+" CAN'T BE a member of anything because it's a prototype ("+classes[className]["filename"]+")");
      exit(1);
  elif "memberOf" in classes[className]:
    if not className in classes:
      j = {
        "autogenerated":getCurrentFilePos(),
        "type":"variable",
        "thisParam":False,
        "name":className,
        "memberOf":classes[className]["memberOf"],
        "generate" : "jswSymbolIndex_"+className+"",
        "return" : ["JsVar"],
        "filename" : classes[className]["filename"]
      }
      classes[className] = j
      jsondatas.append(j)
  else:
    print("WARNING: Class "+className+" is not a member of anything ("+classes[className]["filename"]+")");

try:
  for j in jsondatas:
    if "memberOf" in j:
      if not j["memberOf"] in symbolTables:
        symbolTables[j["memberOf"]] = { "autogenerated":getCurrentFilePos(), "type" : "object", "name" : j["memberOf"], "functions" : [] }
      symbolTables[j["memberOf"]]["functions"].append(j);
    else: print("no member: "+json.dumps(j, sort_keys=True, indent=2))
except:
  print("Unexpected error:", sys.exc_info())
  print(json.dumps(j, sort_keys=True, indent=2))
  exit(1)

# If we have a 'prototype', make sure it's linked back
# into the original class
for sym in symbolTables:
  if sym[-10:]==".prototype":
    className = sym[:-10]
    if not "prototype" in symbolTables[className]["functions"]:
      j = {
        "autogenerated":getCurrentFilePos(),
        "type":"variable",
        "thisParam":False,
        "name":"prototype",
        "memberOf":className,
        "generate" : "jswSymbolIndex_"+className+"_prototype",
        "return" : ["JsVar"],
        "filename" : classes[className]["filename"]
      }
      symbolTables[className]["functions"].append(j)
      jsondatas.append(j)

#print(json.dumps(symbolTables, sort_keys=True, indent=2))
#exit(1)

# ------------------------------------------------------------------------------------------------------
#print(json.dumps(tree, sort_keys=True, indent=2))
# ------------------------------------------------------------------------------------------------------

wrapperFile = open(wrapperFileName,'w')

codeOut('// Automatically generated wrapper file ')
codeOut('// Generated by scripts/build_jswrapper.py');
codeOut('');
codeOut('#include "jswrapper.h"');
codeOut('#include "jsnative.h"');
codeOut('#include "jsparse.h"');
for include in includes:
  codeOut('#include "'+include+'"');
codeOut('');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('// --------------------------------------------------------------- SYMBOL TABLE INDICES    ');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('');

idx = 0
for name in symbolTables:
  symbolTables[name]["indexName"] = "jswSymbolIndex_"+name.replace(".","_");
  symbolTables[name]["index"] = str(idx);
  codeOut("const unsigned char "+symbolTables[name]["indexName"]+" = "+str(idx)+";");
  idx = idx + 1

codeOut('');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('// ----------------------------------------------------------------- AUTO-GENERATED WRAPPERS');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('');

for jsondata in jsondatas:
  if ("generate_full" in jsondata):
    gen_name = "gen_jswrap"
    if "memberOf" in jsondata: gen_name = gen_name + "_" + jsondata["memberOf"].replace(".","_");
    gen_name = gen_name + "_" + jsondata["name"].replace(".","_");

    jsondata["generate"] = gen_name
    s = [ ]

    params = getParams(jsondata)
    result = getResult(jsondata);
    if jsondata["thisParam"]: s.append("JsVar *parent");
    for param in params:
      s.append(toCType(param[1])+" "+param[0]);

    codeOut("/* "+json.dumps(jsondata, sort_keys=True, indent=2).replace("*/","").replace("/*","")+" */")
    codeOut("static "+toCType(result[0])+" "+jsondata["generate"]+"("+", ".join(s)+") {");
    if result[0]:
      codeOut("  return "+jsondata["generate_full"]+";");
    else:
      codeOut("  "+jsondata["generate_full"]+";");
    codeOut("}");
    codeOut('');
  # Include JavaScript functions
  if ("generate_js" in jsondata):
    gen_name = "gen_jswrap"
    if "memberOf" in jsondata: gen_name = gen_name + "_" + jsondata["memberOf"].replace(".","_");
    gen_name = gen_name + "_" + jsondata["name"];
    jsondata["generate"] = gen_name

    s = [ ]
    params = getParams(jsondata)
    result = getResult(jsondata)
    if hasThis(jsondata): s.append("JsVar *parent")
    for param in params:
      if param[1]!="JsVar": FATAL_ERROR("All arguments to generate_js must be JsVars");
      s.append(toCType(param[1])+" "+param[0]);

    js = "";
    with open(basedir+jsondata["generate_js"], 'r') as file:
      js = file.read().strip()
    statement = "jspExecuteJSFunction("+json.dumps(js)
    if hasThis(jsondata): statement = statement + ", parent"
    else: statement = statement + ", NULL"

    codeOut("static "+toCType(result[0])+" "+jsondata["generate"]+"("+", ".join(s)+") {")
    if len(params):
      codeOut("  JsVar *args[] = {");
      for param in params:
        codeOut("    "+param[0]+",")
      codeOut("  };")
      statement = statement + ","+str(len(params))+", args)"
    else: # no args
      statement = statement + ",0,NULL)"

    if result[0]:
      if result[0]!="JsVar": FATAL_ERROR("All arguments to generate_js must be JsVars");
      codeOut("  return "+statement+";")
    else:
      codeOut("  jsvUnLock("+statement+");")
    codeOut("}");
    codeOut('');

codeOut('// -----------------------------------------------------------------------------------------');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('');

# For the ESP8266 we want to put the structures into flash, we need a fresh section 'cause the
# .irom.literal section used elsewhere has different readability attributes, sigh
codeOut("#ifdef ESP8266\n#define FLASH_SECT __attribute__((section(\".irom.literal2\"))) __attribute__((aligned(4)))");
codeOut("#else\n#define FLASH_SECT\n#endif\n");

print("Outputting Symbol Tables")
for name in symbolTables:
  codeOutSymbolTable(symbolTables[name]);
codeOut('');
codeOut('');
codeOut('// If anything in our symbol table has been instantiated already, the ref to it is in here ');
codeOut('JsVarRef jswSymbolTableInstantiations['+str(len(symbolTables))+'];');
codeOut('// The classes/prototypes in our symbol table');
codeOut('const JswSymList jswSymbolTables['+str(len(symbolTables))+'] = {');
for name in symbolTables:
  tab = symbolTables[name]
  codeOut("  {"+", ".join([tab["symbolListName"], tab["symbolTableCount"], tab["symbolTableChars"], tab["constructorPtr"], tab["constructorSpec"]])+"}, // "+tab["indexName"]+", "+name);
codeOut('};');
codeOut('');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('// ------------------------------------------------------------------ symbols for debugging ');
codeOut('');
for name in symbolTables:
  tab = symbolTables[name]
  codeOut("  const JswSymList *jswSymbolTable_"+name.replace(".","_")+" = &jswSymbolTables["+tab["index"]+"]; // "+tab["indexName"]);
codeOut('');
codeOut('// -----------------------------------------------------------------------------------------');
codeOut('// -----------------------------------------------------------------------------------------');

# In jswBinarySearch we used to use READ_FLASH_UINT16 for sym->strOffset and sym->functionSpec for ESP8266
# (where unaligned reads broke) but despite being packed, the structure JswSymPtr is still always an multiple
# of 2 in length so they will always be halfword aligned.
codeOut("""
JsVar *jswCreateFromSymbolTable(int tableIndex) {
  JsVar *v;
  if (jswSymbolTableInstantiations[tableIndex]) {
    v = jsvLock(jswSymbolTableInstantiations[tableIndex]);
    if (jsvIsNativeObject(v) && v->varData.nativeObject == &jswSymbolTables[tableIndex]) {
      return v;
    } else {
      assert(0);
      jswSymbolTableInstantiations[tableIndex] = 0; // uh oh!
    }
  }
  v = jsvNewWithFlags(JSV_OBJECT | JSV_NATIVE);
  if (v) {
    v->varData.nativeObject = &jswSymbolTables[tableIndex];
    jswSymbolTableInstantiations[tableIndex] = jsvGetRef(v);
  }
  return v;
}

void jsvNativeObjectFreed(JsVar *var) {
  assert(jsvIsNativeObject(var));
  int idx = (int)(var->varData.nativeObject - jswSymbolTables);
  jswSymbolTableInstantiations[idx] = 0;
}

""");
codeOut("""
// Binary search coded to allow for JswSyms to be in flash on the esp8266 where they require
// word accesses
JsVar *jswBinarySearch(const JswSymList *symbolsPtr, JsVar *parent, const char *name) {
  uint8_t symbolCount = READ_FLASH_UINT8(&symbolsPtr->symbolCount);
  int searchMin = 0;
  int searchMax = symbolCount - 1;
  while (searchMin <= searchMax) {
    int idx = (searchMin+searchMax) >> 1;
    const JswSymPtr *sym = &symbolsPtr->symbols[idx];
    int cmp = FLASH_STRCMP(name, &symbolsPtr->symbolChars[sym->strOffset]);
    if (cmp==0) {
      unsigned short functionSpec = sym->functionSpec;
      if ((functionSpec & JSWAT_CALLINFO_MASK) == JSWAT_EXECUTE_IMMEDIATELY)
        return jsnCallFunction(sym->functionPtr, functionSpec, parent, 0, 0);
      if ((functionSpec & JSWAT_CALLINFO_MASK) == JSWAT_SYMBOL_TABLE)
        return jswCreateFromSymbolTable((int)(size_t)sym->functionPtr);
      return jsvNewNativeFunction(sym->functionPtr, functionSpec);
    } else {
      if (cmp<0) {
        // searchMin is the same
        searchMax = idx-1;
      } else {
        searchMin = idx+1;
        // searchMax is the same
      }
    }
  }
  return 0;
}

""");

codeOut('')
codeOut('')

codeOut('int jswGetSymbolIndexForObject(JsVar *var) {')
codeOut('  if (jsvIsRoot(var)) {');
codeOut('    return jswSymbolIndex_global;');
codeOut('  }');
codeOut('  if (jsvIsNativeObject(var)) {');
codeOut('    assert(var->varData.nativeObject);');
codeOut('    return (int)(var->varData.nativeObject-jswSymbolTables);'); # fixme - why not store int??
codeOut('  }');
codeOut('  //FIXME: should group jsvIsArrayBuffer tests')
for className in objectChecks.keys():
  if not (className+".prototype") in symbolTables: # eg it's not in jswGetSymbolIndexForObjectProto
    codeOut("  if ("+objectChecks[className]+") return jswSymbolIndex_"+className+";")
codeOut("  return -1;")
codeOut('}')

codeOut('')
codeOut('')

codeOut('int jswGetSymbolIndexForObjectProto(JsVar *var) {')
codeOut('  // Instantiated objects, so we should point to the prototypes of the object itself');
codeOut(' //FIXME - see build_jswrapper.py')
for className in objectChecks.keys():
  if not className=="global": # we did 'global' above
    if (className+".prototype") in symbolTables:
      codeOut("  if ("+objectChecks[className]+") return jswSymbolIndex_"+className+"_prototype;")
codeOut("  return -1;")
codeOut('}')

codeOut("""


const JswSymList *jswGetSymbolListForObject(JsVar *var) {
  int symIdx = jswGetSymbolIndexForObject(var);
  return (symIdx>=0) ? &jswSymbolTables[symIdx] : 0;
}


const JswSymList *jswGetSymbolListForObjectProto(JsVar *var) {
  int symIdx = jswGetSymbolIndexForObjectProto(var);
  return (symIdx>=0) ? &jswSymbolTables[symIdx] : 0;
}

// For instances of builtins like Pin, String, etc, search in X.prototype
JsVar *jswFindInObjectProto(JsVar *parent, const char *name) {
  int symIdx = jswGetSymbolIndexForObjectProto(parent);
  if (symIdx>=0) {
    if (!strcmp(name,"__proto__")) // we're actually looking for the prototype itself! just return it
      return jswCreateFromSymbolTable(symIdx);
    return jswBinarySearch(&jswSymbolTables[symIdx], parent, name);
  }
  return 0;
}

JsVar *jswFindBuiltIn(JsVar *parentInstance, JsVar *parent, const char *name) {
  if (jsvIsRoot(parent)) {
    #ifndef ESPR_EMBED
    // Check to see whether we're referencing a pin? Should really be in symbol table...
    Pin pin = jshGetPinFromString(name);
    if (pin != PIN_UNDEFINED) {
      return jsvNewFromPin(pin);
    }
    #endif
  }
  int symIdx = jswGetSymbolIndexForObject(parent);
  if (symIdx>=0) return jswBinarySearch(&jswSymbolTables[symIdx], parentInstance, name);
  return 0;
}

""");


builtinChecks = []
for jsondata in jsondatas:
  if "memberOf" in jsondata:
    if not jsondata["memberOf"] in libraries and jsondata["memberOf"].find(".")<0:
      check = 'strcmp(name, "'+jsondata["memberOf"]+'")==0';
      if not check in builtinChecks:
        builtinChecks.append(check)


codeOut('bool jswIsBuiltInObject(const char *name) {')
codeOut('  return\n'+" ||\n    ".join(builtinChecks)+';')
codeOut('}')

codeOut('')
codeOut('')


codeOut('JsVar *jswGetBuiltInLibrary(const char *name) {')
for lib in libraries:
  codeOut('  if (strcmp(name, "'+lib+'")==0) return jswCreateFromSymbolTable(jswSymbolIndex_'+lib+');');
codeOut('  return 0;')
codeOut('}')

codeOut('')
codeOut('')

codeOut('/** Given a variable, return the basic object name of it */')
codeOut('const char *jswGetBasicObjectName(JsVar *var) {')
codeOut('  if (jsvIsArrayBuffer(var)) {')
for className in objectChecks.keys():
  if objectChecks[className].startswith("jsvIsArrayBuffer(var) && "):
    codeOut("    if ("+objectChecks[className][25:]+") return \""+className+"\";")
codeOut('  }')
for className in objectChecks.keys():
  if not objectChecks[className].startswith("jsvIsArrayBuffer(var) && "):
    codeOut("  if ("+objectChecks[className]+") return \""+className+"\";")
codeOut('  return 0;')
codeOut('}')

codeOut('')
codeOut('')


codeOut("/** Tasks to run on Idle. Returns true if either one of the tasks returned true (eg. they're doing something and want to avoid sleeping) */")
codeOut('bool jswIdle() {')
codeOut('  bool wasBusy = false;')
for jsondata in jsondatas:
  if "type" in jsondata and jsondata["type"]=="idle":
    codeOut("  if ("+jsondata["generate"]+"()) wasBusy = true;")
codeOut('  return wasBusy;')
codeOut('}')

codeOut('')
codeOut('')

codeOut("/** Tasks to run on Hardware Initialisation (called once at boot time, after jshInit, before jsvInit/etc) */")
codeOut('void jswHWInit() {')
for jsondata in jsondatas:
  if "type" in jsondata and jsondata["type"]=="hwinit":
    codeOut("  "+jsondata["generate"]+"();")
codeOut('}')

codeOut('')
codeOut('')

codeOut("/** Tasks to run on Initialisation (eg boot/load/reset/after save/etc) */")
codeOut('void jswInit() {')
codeOut('// Ensure we set up our list of instantiated builtins')
codeOut('unsigned int varsSize = jsvGetMemoryTotal();')
codeOut('for (JsVarRef i=1;i<=varsSize;i++) {')
codeOut('  JsVar *var = _jsvGetAddressOf(i);')
codeOut('  if (jsvIsNativeObject(var)) {')
codeOut('    int idx = (int)(var->varData.nativeObject - jswSymbolTables);')
codeOut('    jswSymbolTableInstantiations[idx] = i;')
codeOut('  }')
codeOut('}')
codeOut("// call other libraries' init methods");
if jsbootcode!=False:
  codeOut('  jsvUnLock(jspEvaluate('+json.dumps(jsbootcode)+', true/*static*/));')
for jsondata in jsondatas:
  if "type" in jsondata and jsondata["type"]=="init":
    codeOut("  "+jsondata["generate"]+"();")
codeOut('}')

codeOut('')
codeOut('')

codeOut("/** Tasks to run on Deinitialisation (eg before save/reset/etc) */")
codeOut('void jswKill() {')
codeOut("  // call other libraries' init methods")
for jsondata in jsondatas:
  if "type" in jsondata and jsondata["type"]=="kill":
    codeOut("  "+jsondata["generate"]+"();")
codeOut("  // reset our list of instantiated builtins")
codeOut('  memset(jswSymbolTableInstantiations, 0, sizeof(jswSymbolTableInstantiations));')
codeOut('}')

codeOut("/** Tasks to run when a character event is received */")
codeOut('bool jswOnCharEvent(IOEventFlags channel, char charData) {')
codeOut('  NOT_USED(channel);')
codeOut('  NOT_USED(charData);')
for jsondata in jsondatas:
  if "type" in jsondata and jsondata["type"].startswith("EV_"):
    codeOut("  if (channel=="+jsondata["type"]+") return "+jsondata["generate"]+"(charData);")
codeOut('  return false;')
codeOut('}')

codeOut("/** If we have a built-in module with the given name, return the module's contents - or 0 */")
codeOut('const char *jswGetBuiltInJSLibrary(const char *name) {')
codeOut('  NOT_USED(name);')
for modulename in jsmodules:
  codeOut("  if (!strcmp(name,\""+modulename+"\")) return "+json.dumps(jsmodules[modulename])+";")
codeOut('  return 0;')
codeOut('}')

codeOut('')
codeOut('')

codeOut('const char *jswGetBuiltInLibraryNames() {')
librarynames = []
for lib in libraries:
  librarynames.append(lib);
for lib in jsmodules:
  librarynames.append(lib);
codeOut('  return "'+','.join(librarynames)+'";')
codeOut('}')

codeOut('#ifdef USE_CALLFUNCTION_HACK')
codeOut('// on Emscripten and i386 we cant easily hack around function calls with floats/etc, plus we have enough')
codeOut('// resources, so just brute-force by handling every call pattern we use in a switch')
codeOut('JsVar *jswCallFunctionHack(void *function, JsnArgumentType argumentSpecifier, JsVar *thisParam, JsVar **paramData, int paramCount) {')
codeOut('  switch((int)argumentSpecifier) {')
#for argSpec in argSpecs:
#  codeOut('  case '+argSpec+":")
argSpecs = []
for jsondata in jsondatas:
  if "generate" in jsondata:
    argSpec = getArgumentSpecifier(jsondata)
    if ("JSWAT_EXECUTE_IMMEDIATELY" in argSpec) or ("JSWAT_SYMBOL_TABLE" in argSpec): continue;
    if not argSpec in argSpecs:
      argSpecs.append(argSpec)
      params = getParams(jsondata)
      result = getResult(jsondata);
      pTypes = []
      pValues = []
      if hasThis(jsondata):
        pTypes.append("JsVar*")
        pValues.append("thisParam")
      cmd = "";
      cmdstart = "";
      cmdend = "";
      n = 0
      for param in params:
        pTypes.append(toCType(param[1]));
        if param[1]=="JsVarArray":
          cmdstart =  "      JsVar *argArray = (paramCount>"+str(n)+")?jsvNewArray(&paramData["+str(n)+"],paramCount-"+str(n)+"):jsvNewEmptyArray();\n";
          pValues.append("argArray");
          cmdend = "      jsvUnLock(argArray);\n\n";
        else:
          pValues.append(toCUnbox(param[1])+"((paramCount>"+str(n)+")?paramData["+str(n)+"]:0)");
        n = n+1

      codeOut("    case "+argSpec+": {");
      codeOut("      JsVar *result = 0;");
      if cmdstart:  codeOut(cmdstart);
      cmd = "(("+toCType(result[0])+"(*)("+",".join(pTypes)+"))function)("+",".join(pValues)+")";
      if result[0]: codeOut("      result = "+toCBox(result[0])+"("+cmd+");");
      else: codeOut("      "+cmd+";");
      if cmdend:  codeOut(cmdend);
      codeOut("      return result;");
      codeOut("    }");




#((uint32_t (*)(size_t,size_t,size_t,size_t))function)(argData[0],argData[1],argData[2],argData[3]);
codeOut('  default: jsExceptionHere(JSET_ERROR,"Unknown argspec %d",argumentSpecifier);')
codeOut('  }')
codeOut('  return 0;')
codeOut('}')
codeOut('#endif')

codeOut('')
codeOut('')
