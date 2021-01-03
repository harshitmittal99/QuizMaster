import socket
import pickle
import time
import json
from enum import Enum
import struct
from threading import Thread
from threading import Lock
from threading import Event
BUFFER_SIZE = 1024

RestartEvent = False

class States(Enum):
    initial = 1
    TopicSelection = 2
    Questioned = 3
    Answered = 4
    Terminated = 5

my_socket = socket.socket()      # Create a socket object
my_host = socket.gethostname()     # Get local machine name
my_port = 5034# Store a port for your service.
my_socket.connect_ex((my_host, my_port))
my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)    
state = States.initial
print("connected")

class headers(Enum):
    TopicSelection = 1
    PersonalMessage = 2
    BroadCastMessage = 3
    FinalAnswer = 4
    NewAddition = 5
    Question = 6
    next = 8
    Restart = 9


def send_msg(sock, msg,message_type):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('i',message_type.value)+struct.pack('i', len(msg)) + msg
    sock.sendall(msg)

def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = sock.recv(4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('i', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(BUFFER_SIZE)
        if not packet:
            return None
        data.extend(packet)
    return data

def Individual():
    all_topics = my_socket.recv(BUFFER_SIZE)
    print("Individual Mode Selected")
    all_topics = pickle.loads(all_topics)
    print("select topic for next question")
    for i in range(len(all_topics)):
        print(i+1,end='')
        print('.',all_topics[i])
    selected_topic = input()
    my_socket.sendall(selected_topic.encode('utf-8'))
    Question = my_socket.recv(BUFFER_SIZE)
    Question = pickle.loads(Question)
    print(Question["Question"])
    if "Options" in Question:
        print("A.",Question["Options"][0])
        print("B.",Question["Options"][1])
        print("C.",Question["Options"][2])
        print("D.",Question["Options"][3])
    answer = input()
    my_socket.send(answer.encode('utf-8'))
    comp_result = my_socket.recv(BUFFER_SIZE)
    comp_result = pickle.loads(comp_result)
    result = comp_result[0]
    correct_ans = comp_result[1]
    Explanation = comp_result[2]
    if result:
        print("Correct Answer")
        print("Explanation: ", Explanation)
    else:
        print("Your Answer is Wrong")
        print("Correct Answer is : ",correct_ans)
        print("Explanation: ",Explanation)
    print("Enter n to attempt next Question")
    print("q to quit")
    print("r to return")
    next = input()
    my_socket.send(next.encode('utf-8'))
    if next == 'n':
        Individual()
    elif next == 'r':
        Setup()


import re
patterns = {headers.PersonalMessage:"^@[0-9]+\s*:",headers.BroadCastMessage:"^@all\s*:",}

def read_input():
    global state
    while True:
        if state == States.Terminated:
            break
        data = input()
        message_type = ""
        for pattern in patterns:
            if re.search(patterns[pattern],data):
                message_type = pattern
                break
        if message_type == headers.BroadCastMessage:
            msg = pickle.dumps(data.split(":")[1])
            send_msg(my_socket,msg,message_type)
        elif message_type == headers.PersonalMessage:
            rcvr,msg = data.split(':')
            rcvr = int(rcvr[1:])
            rcvr = struct.pack('i',rcvr)
            msg = pickle.dumps(msg)
            send_msg(my_socket,rcvr+msg,headers.PersonalMessage)
        else:
            data = pickle.dumps(data)
            if state == States.TopicSelection:
                send_msg(my_socket,data,headers.TopicSelection)
            elif state == States.Questioned:
                send_msg(my_socket,data,headers.FinalAnswer)
            elif state == States.Answered:
                send_msg(my_socket,data,headers.next)
                data = pickle.loads(data)
                if data == 'n':
                    state = States.initial
                elif data == 'r':
                    state = States.initial
                    break
                elif data == 'q':
                    state = States.Terminated
                    break


def recvMsg():
    while True:
        if state == States.Terminated:
            break
        message_type = my_socket.recv(4)
        if not message_type:
            break
        if message_type == struct.pack('????',False,False,False,False):
            break
        message_type = struct.unpack('i',message_type)[0]
        handle_messages[headers(message_type)]()


def NewAddition():
    global state
    state= States.TopicSelection
    member_and_topics = pickle.loads(recv_msg(my_socket))
    all_members = member_and_topics[0]
    all_topics = member_and_topics[1]
    for member in all_members:
        print(member[1],"has user id",member[0])
    print("Select from Topics Below")
    for topic in all_topics:
        print(topic)

def PersonalMessage():
    msg = recv_msg(my_socket)
    sender = msg[:4]
    msg = msg[4:]
    sender = struct.unpack('i',sender)[0]
    msg = pickle.loads(msg)
    print("Message from",sender,":",msg)

def BroadCast():
    msg = recv_msg(my_socket)
    sender = msg[:4]
    msg = msg[4:]
    sender = struct.unpack('i',sender)[0]
    msg = pickle.loads(msg)
    print("Broadcasted Message from",sender,":",msg)

def Question():
    global state
    state = States.Questioned
    msg = recv_msg(my_socket)
    sender = msg[:4]
    sender = struct.unpack('i',sender)[0]
    msg = msg[4:]
    msg = pickle.loads(msg)
    TopicSelected = msg["Topic"]
    print(TopicSelected,"Topic Seleceted by user ID",sender)
    if msg["qtype"]:
        print("Question-",msg["Question"])
        print("A.",msg["Options"][0],end = '\t\t\t')
        print("B.",msg["Options"][1])
        print("C.",msg["Options"][2],end = '\t\t\t')
        print("D.",msg["Options"][3])
    else:
        print("Question-",msg["Question"])

def FinalAnswer():
    global state
    state = States.Answered
    msg = recv_msg(my_socket)
    sender = msg[:4]
    sender = struct.unpack('i',sender)[0]
    msg = msg[4:]
    msg = pickle.loads(msg)
    AnswerSelected = msg[0]
    print("Answer Selected By",sender,":",AnswerSelected)
    result = msg[2]
    Explanation = msg[3]
    if result:
        print("Correct")
        print("Explanation:",Explanation)
    else:
        print("Incorrect")
        CorrectAnswer = msg[1]
        print("Correct Answer is:",CorrectAnswer)
        print("Explanation:",Explanation)

handle_messages = {
    headers.NewAddition : NewAddition,
    headers.PersonalMessage: PersonalMessage,
    headers.Question: Question,
    headers.BroadCastMessage: BroadCast,
    headers.FinalAnswer: FinalAnswer
}

def Group():
    InputThread = Thread(target = read_input)
    RecvThread = Thread(target= recvMsg)
    InputThread.start()
    RecvThread.start()
    InputThread.join()
    RecvThread.join()
    if state == States.initial:
        Setup()


MyName = input("Enter Your Name: ")
my_socket.sendall(pickle.dumps(MyName))
id = my_socket.recv(1024)
ClientId = int.from_bytes(id,"little")
print("Welcome {0} User ID {1}".format(MyName,ClientId))
def Setup():
    print("Press I for Individual mode")
    print("Press G for Group mode")
    print("Press A for Admin mode")
    mode = input()
    while(mode != 'I' and mode != 'G' and mode !='A'):
        print("Please Enter Valid Input")
        mode = input()
    my_socket.send(mode.encode('utf-8'))
    if(mode == "I"):
        Individual()
    elif(mode == 'G'):
        all_groups = my_socket.recv(BUFFER_SIZE)
        all_groups = pickle.loads(all_groups)
        print(*all_groups)
        GrpID = input("Enter Group ID or Enter new to make new group: ")
        GrpID = pickle.dumps(GrpID)
        my_socket.sendall(GrpID)
        Groupreq = my_socket.recv(1)
        Groupreq = struct.unpack('?',Groupreq)[0]
        while(not Groupreq):
            GrpID = input("This group has initiated test. Please Select some other group or enter new to create new group:")
            GrpID = pickle.dumps(GrpID)
            my_socket.sendall(GrpID)
            Groupreq = my_socket.recv(1)
            Groupreq = struct.unpack('?',Groupreq)[0]
        Group()

Setup()

my_socket.close()