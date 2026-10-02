cmake_minimum_required(VERSION 3.10)
project(camera_bridge CXX)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_BUILD_TYPE Release)

# Deptrum Aurora 900 series SDK (kept in ~/robot_app/vendor/camera/sdk on the robot)
set(DEPTRUM_SDK "$ENV{HOME}/robot_app/vendor/camera/sdk" CACHE PATH "Deptrum SDK root")
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)
find_package(Threads REQUIRED)

add_executable(camera_bridge camera_bridge.cc)
target_include_directories(camera_bridge PRIVATE ${DEPTRUM_SDK}/include ${OpenCV_INCLUDE_DIRS})
target_link_libraries(camera_bridge ${DEPTRUM_SDK}/lib/libdeptrum_stream_aurora900.so ${OpenCV_LIBS} Threads::Threads)
set_target_properties(camera_bridge PROPERTIES BUILD_RPATH "${DEPTRUM_SDK}/lib" INSTALL_RPATH "${DEPTRUM_SDK}/lib")
