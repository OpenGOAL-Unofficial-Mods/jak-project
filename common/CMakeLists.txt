function(write_revision_h)
    find_package(Git)
    set(GIT_SHORT_SHA "")
    set(GIT_TAG "")
    if(NOT GIT_FOUND)
      MESSAGE(STATUS "write_revision_h(): git was not found")
    endif()
    MESSAGE(STATUS "write_revision_h(): ${CMAKE_SOURCE_DIR}")
    if (GIT_FOUND AND EXISTS ${CMAKE_SOURCE_DIR}/.git)
        MESSAGE(STATUS "Git found, using it to get revision info")
        EXECUTE_PROCESS(WORKING_DIRECTORY ${CMAKE_SOURCE_DIR} COMMAND ${GIT_EXECUTABLE} rev-parse --short HEAD
                OUTPUT_VARIABLE GIT_SHORT_SHA
                OUTPUT_STRIP_TRAILING_WHITESPACE)
        EXECUTE_PROCESS(WORKING_DIRECTORY ${PROJECT_SOURCE_DIR} COMMAND ${GIT_EXECUTABLE} tag --points-at HEAD
                OUTPUT_VARIABLE GIT_TAG
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_QUIET)
    endif()
    file(WRITE ${CMAKE_CURRENT_SOURCE_DIR}/versions/revision.h "#define BUILT_TAG \"${GIT_TAG}\"\n#define BUILT_SHA \"${GIT_SHORT_SHA}\"\n")
endfunction()

write_revision_h()

add_library(common
        versions/versions.cpp
        audio/audio_formats.cpp
        cross_os_debug/xdbg.cpp
        cross_sockets/XSocket.cpp
        cross_sockets/XSocketServer.cpp
        cross_sockets/XSocketClient.cpp
        custom_data/pack_helpers.cpp
        custom_data/TFrag3Data.cpp
        dma/dma.cpp
        dma/dma_copy.cpp
        dma/gs.cpp
        global_profiler/GlobalProfiler.cpp
        goos/Interpreter.cpp
        goos/Object.cpp
        goos/ParseHelpers.cpp
        goos/Printer.cpp
        goos/PrettyPrinter.cpp
        goos/PrettyPrinter2.cpp
        goos/Reader.cpp
        goos/TextDB.cpp
        repl/config.cpp
        repl/util.cpp
        log/log.cpp
        math/geometry.cpp
        repl/nrepl/ReplClient.cpp
        repl/nrepl/ReplServer.cpp
        type_system/defenum.cpp
        type_system/deftype.cpp
        type_system/state.cpp
        type_system/Type.cpp
        type_system/TypeFieldLookup.cpp
        type_system/TypeSpec.cpp
        type_system/TypeSystem.cpp
        serialization/subtitles/subtitles_ser.cpp
        serialization/subtitles/subtitles_deser.cpp
        util/Assert.cpp
        util/BitUtils.cpp
        util/compress.cpp
        util/crc32.cpp
        util/dgo_util.cpp
        util/DgoReader.cpp
        util/DgoWriter.cpp
        util/diff.cpp
        util/FileUtil.cpp
        util/FontUtils.cpp
        util/json_util.cpp
        util/read_iso_file.cpp
        util/SimpleThreadGroup.cpp
        util/string_util.cpp
        util/Timer.cpp
        util/os.cpp
        util/print_float.cpp
        util/FrameLimiter.cpp
        util/unicode_util.cpp
        util/term_util.cpp  )

target_link_libraries(common fmt lzokay replxx libzstd_static)

if(WIN32)
    target_link_libraries(common wsock32 ws2_32 windowsapp)
elseif(APPLE)
    # don't need anything special
else()
    target_link_libraries(common stdc++fs)
endif()
