#!/bin/bash
# Script to run Ksoloti with the Homebrew OpenJDK

# Extra JVM arguments
HEAP_JVM_ARGS='-Xms256m -Xmx2g'
MARLIN_JVM_ARGS='-Xbootclasspath/a:lib/marlin-0.9.4.8-Unsafe-OpenJDK11.jar -Dsun.java2d.renderer=org.marlin.pisces.MarlinRenderingEngine -Dsun.java2d.d3d=false'

if [ -f dist/Ksoloti.jar ]; then
    # Use Homebrew OpenJDK if available
    if [ -f /opt/homebrew/opt/openjdk/bin/java ]; then
        echo "Using Homebrew OpenJDK..."
        /opt/homebrew/opt/openjdk/bin/java -Xdock:name=Ksoloti $HEAP_JVM_ARGS $MARLIN_JVM_ARGS -jar dist/Ksoloti.jar "$@" 2>&1 | tee "ksoloti.log"
    else
        echo "Homebrew OpenJDK not found, trying system Java..."
        java -Xdock:name=Ksoloti $HEAP_JVM_ARGS $MARLIN_JVM_ARGS -jar dist/Ksoloti.jar "$@" 2>&1 | tee "ksoloti.log"
    fi
else
    echo "Ksoloti.jar does not exist. Please build the project first."
    exit 1
fi 