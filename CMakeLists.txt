cmake_minimum_required(VERSION 3.31)
project(waygui C)

set(CMAKE_C_STANDARD 11)

add_library(${PROJECT_NAME} SHARED waygui/waygui.c
        waygui/wire.c
        waygui/helpers.c
)
#target_compile_options(${PROJECT_NAME} PRIVATE "-fvisibility=hidden")
install(FILES waygui/wire.h DESTINATION include/)

