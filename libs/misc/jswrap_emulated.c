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
 * This file is designed to be parsed during the build process
 *
 * Stubs for emulation (eg NRF class)
 * ----------------------------------------------------------------------------
 */
#include <jswrap_emulated.h>

/* DO_NOT_INCLUDE_IN_DOCS - this is a special token for common.py */

/*JSON{
  "type" : "object",
  "name" : "NRF"
}

*/
/*JSON{
  "type" : "object",
  "name" : "Bluetooth"
}

*/

/*JSON{
  "type" : "function",
  "name" : "getSecurityStatus",
  "memberOf" : "NRF",
  "thisParam" : false,
  "generate_full" : "jsvNewObject()",
  "return" : ["JsVar","An object"],
  "return_object" : "NRFSecurityStatus"
}

*/
/*JSON{
  "type" : "function",
  "name" : "getAddress",
  "memberOf" : "NRF",
  "thisParam" : false,
  "generate_full" : "jsvNewFromString(\"12:34:56:78:90:ab\")",
  "return" : ["JsVar","An object"]
}

*/
/*JSON{
  "type" : "function",
  "name" : "setServices",
  "memberOf" : "NRF",
  "thisParam" : false,
  "generate_full" : "",
  "params" : [
    ["data","JsVar","The service (and characteristics) to advertise"],
    ["options","JsVar","Optional object containing options"]
  ]
}

*/
/*JSON{
  "type" : "function",
  "name" : "setAdvertising",
  "memberOf" : "NRF",
  "thisParam" : false,
  "generate_full" : "",
  "params" : [
    ["data","JsVar","The data to advertise as an object - see below for more info"],
    ["options","JsVar","[optional] An object of options"]
  ]
}

*/
/*JSON{
  "type" : "function",
  "name" : "setConsole",
  "memberOf" : "Bluetooth",
  "thisParam" : false,
  "generate_full" : ""
}

*/
