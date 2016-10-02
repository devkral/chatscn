#! /usr/bin/bash
testdirserver="$HOME/.kivytestserver"
testdir1="$HOME/.kivytest1"
testdir2="$HOME/.kivytest2"

mkdir -p "$testdirserver"
mkdir -p "$testdir1"
mkdir -p "$testdir2"


python -m simplescn client "--nounix=False" "--config=$testdir1" "--run=/tmp/client1" &
python -m simplescn client "--nounix=False" "--config=$testdir2" "--run=/tmp/client2" &
sleep 5
XDG_CONFIG_HOME="$testdir1" python ./chatscn "/tmp/client1/$UID-simplescn-client/socket" &
XDG_CONFIG_HOME="$testdir2" python ./chatscn "/tmp/client2/$UID-simplescn-client/socket" &
#trap "kill -SIGINT %1; kill -SIGINT %1; kill -SIGINT %1; exit 0" SIGINT SIGTERM
python -m simplescn server "--config=$testdirserver"
exit 0
