#!/bin/sh
set -e
mkdir -p build
cp A1.java test/TestA1.java datafile1.txt build/
cd build
curl -s -L -o junit.jar https://repo1.maven.org/maven2/junit/junit/4.13.2/junit-4.13.2.jar
curl -s -L -o hamcrest.jar https://repo1.maven.org/maven2/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar
javac -cp junit.jar:hamcrest.jar:. A1.java TestA1.java
java -cp .:junit.jar:hamcrest.jar org.junit.runner.JUnitCore TestA1
cd ..
rm -rf build
