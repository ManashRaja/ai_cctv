#!/bin/sh

sudo apt-get update &&
sudo apt-get install build-essential cmake git pkg-config &&
sudo apt-get install libjpeg8-dev libtiff4-dev libjasper-dev libpng12-dev &&
sudo apt-get install libgtk2.0-dev &&
sudo apt-get install libavcodec-dev libavformat-dev libswscale-dev libv4l-dev &&
sudo apt-get install libatlas-base-dev gfortran &&
wget https://bootstrap.pypa.io/get-pip.py &&
sudo python get-pip.py &&
rm get-pip.py &&
sudo apt-get install python2.7-dev &&

cd ~ &&
git clone https://github.com/Itseez/opencv.git || true &&
cd opencv &&
git checkout 3.0.0 &&
cd ~ &&
git clone https://github.com/Itseez/opencv_contrib.git || true &&
cd opencv_contrib &&
git checkout 3.0.0 &&
cd ~/opencv &&
mkdir -p build &&
cd build &&
cmake -D CMAKE_BUILD_TYPE=RELEASE -D CMAKE_INSTALL_PREFIX=/usr/local -D INSTALL_C_EXAMPLES=ON -D INSTALL_PYTHON_EXAMPLES=ON -D OPENCV_EXTRA_MODULES_PATH=~/opencv_contrib/modules -D BUILD_EXAMPLES=ON .. &&
make &&
sudo make install &&
sudo ldconfig &&

sudo pip install -r requirements.txt
