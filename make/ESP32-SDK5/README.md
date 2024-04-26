# ESP32 SDK5 test build

**This is a very quick hack - there's still a lot to change**

```

# first go to the Espruino root dir and run 'make clean;BOARD=ESP32 make' to set up platform_config

# Initial SDK setup
cd esp5.2.1
git clone -b v5.2.1 --recursive https://github.com/espressif/esp-idf.git
# --depth 1 ?
cd esp-idf
./install.sh esp32,esp32c2,esp32c3

# Now build
. ./export.sh
cd ../../make/ESP32-SDK5/
idf.py set-target esp32

idf.py menuconfig

component - > FreeRTOS -> Kernel -> CONFIG_FREERTOS_ENABLE_BACKWARD_COMPATIBILITY must be enabled

idf.py build 2>&1 | grep --color=always -e "^" -e "error"
```
