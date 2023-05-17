/*
 * This file is part of Espruino, a JavaScript interpreter for Microcontrollers
 *
 * Copyright (C) 2013 Gordon Williams <gw@pur3.co.uk>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * ----------------------------------------------------------------------------
 * Header for auto-generated Wrapper functions
 * ----------------------------------------------------------------------------
 */

#ifndef JSWRAPPER_H_
#define JSWRAPPER_H_

#include "jsutils.h"
#include "jsvar.h"
#include "jsdevices.h"

/// Do a binary search of the symbol table list
JsVar *jswBinarySearch(const JswSymList *symbolsPtr, JsVar *parent, const char *name);

// For instances of builtins like Pin, String, etc, search in X.prototype
JsVar *jswFindInObjectProto(JsVar *parent, const char *name);

/** If 'name' is something that belongs to an internal function, execute it.
 * parentInstance is the actual object ('this'), but parent may be a prototype of another object */
JsVar *jswFindBuiltIn(JsVar *parentInstance, JsVar *parent, const char *name);

/// Given an object, return the list of symbols for it
const JswSymList *jswGetSymbolListForObject(JsVar *parent);

/// Given an object, return the list of symbols for its prototype
const JswSymList *jswGetSymbolListForObjectProto(JsVar *parent);

/// Given the name of an Object, see if we should set it up as a builtin or not
bool jswIsBuiltInObject(const char *name);

/// Called when we free a NativeObject as we might have to update our mapping to remove it
void jsvNativeObjectFreed(JsVar *var);

/** Given a variable, return the basic object name of it */
const char *jswGetBasicObjectName(JsVar *var);

/** Tasks to run on Idle. Returns true if either one of the tasks returned true (eg. they're doing something and want to avoid sleeping) */
bool jswIdle();

/** Tasks to run on Hardware Initialisation (called once at boot time, after jshInit, before jsvInit/etc) */
void jswHWInit();

/** Tasks to run on Initialisation */
void jswInit();

/** Tasks to run on Deinitialisation */
void jswKill();

/** Tasks to run when a character is received on a certain event channel. True if handled and shouldn't go to IRQ */
bool jswOnCharEvent(IOEventFlags channel, char charData);

/** If we get this in 'require', do we have the object for this
  inside the interpreter already? If so, return a JsVar for the
  native object representing it. */
JsVar *jswGetBuiltInLibrary(const char *name);

/** If we have a built-in JS module with the given name, return the module's contents - or 0.
 * These can be added using teh followinf in the Makefile/BOARD.py file:
 *
 * JSMODULESOURCES+=path/to/modulename:path.js
 * JSMODULESOURCES+=modulename:path/to/module.js
 * JSMODULESOURCES+=_:code_to_run_at_startup.js
 *
 *  */
const char *jswGetBuiltInJSLibrary(const char *name);

/** Return a comma-separated list of built-in libraries */
const char *jswGetBuiltInLibraryNames();

#ifdef USE_CALLFUNCTION_HACK
// on Emscripten and i386 we cant easily hack around function calls with floats/etc, plus we have enough
// resources, so just brute-force by handling every call pattern we use in a switch
JsVar *jswCallFunctionHack(void *function, JsnArgumentType argumentSpecifier, JsVar *thisParam, JsVar **paramData, int paramCount);
#endif

// These are used for checking objects are the correct type
extern const JswSymList *jswSymbolTable_Object_prototype;
extern const JswSymList *jswSymbolTable_Promise_prototype;


/** Given the index of some item in the symbol table, create a 'Native Object'
 * that represents it. This is a JS object that can contain fields, but
 * it is also tagged so that it also contains all the items in the relevant
 * symbol table of built-in items.
 *
 * Takes an argument of the form: jswSymbolIndex_XYZ
 */
JsVar *jswCreateFromSymbolTable(int symbolIndex);

extern const unsigned char jswSymbolIndex_AES;
extern const unsigned char jswSymbolIndex_HASH;


#endif // JSWRAPPER_H_
