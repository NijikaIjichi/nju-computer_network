#!/bin/bash
source /home/njucs/switchyard/syenv/bin/activate

num=100
length=100

if [ $# -gt 1 ]
then
    if [ $2 == "text" ]
    then
        input="input=tmp/send.txt"
        output="output=tmp/recv.txt"
    elif [ $2 == "pic" ]
    then
        num=1024
        length=1024
        input="input=tmp/send.jpg"
        output="output=tmp/recv.jpg"
    fi
fi

if [ $# -gt 0 ]
then
    if [ $1 == "mid" ]
    then
        swyard middlebox.py -g "dropRate=0.19"
    elif [ $1 == "er" ]
    then
        swyard blaster.py -g "blasteeIp=192.168.200.1 num=${num} length=${length} senderWindow=5 timeout=300 recvTimeout=100 ${input}"
    elif [ $1 == "ee" ]
    then
        swyard blastee.py -g "blasterIp=192.168.100.1 num=${num} ${output}"
    fi
fi
