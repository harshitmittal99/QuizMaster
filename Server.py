import socket
import threading
import pickle
import time
import mysql.connector
import json
from threading import Thread 
import ctypes
import struct
from enum import Enum
from socketserver import ThreadingMixIn 
UserID = 0
GroupID = 0
GroupIDLock = threading.Lock()
BUFFER_SIZE = 1024
db = mysql.connector.connect(
    host="localhost",
    user = "Harshit",
    password = "Harshit",
    database = "QuizMaster"
)
def send_msg(sock, msg,message_type):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('i',message_type.value)+struct.pack('i', len(msg)) + msg
    sock.sendall(msg)

def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = sock.recv( 4)
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
all_groups = {}
msg = "HI1"
msg = msg.encode('utf-8')





    

class Group(Thread):
    class States(Enum):
        initial = 1
        questioned = 2
        Answered = 3
        Terminated = 4
    class headers(Enum):
        TopicSelection = 1
        PersonalMessage = 2
        BroadCastMessage = 3
        FinalAnswer = 4
        NewAddition = 5
        Question = 6
        next = 8
        Restart = 9
    def __init__(self,GroupID,client):
        Thread.__init__(self)
        self.handle_messages = {
            Group.headers.TopicSelection: self.SelectTopic,
            Group.headers.BroadCastMessage: self.BroadCast,
            Group.headers.FinalAnswer: self.CheckAnswer,
            Group.headers.PersonalMessage: self.PersonalMessage,
            Group.headers.next: self.NextStep
        }
        self.ID = GroupID
        self.state = self.States.initial
        self.members = {}
        self.members[client.user_id] = client
        self.ActiveMembers = 0
        AllTopics = pickle.dumps([[],all_topics])    
        send_msg(client.conn,AllTopics,Group.headers.NewAddition)
    
    def AddMember(self,client):
        if self.state != self.States.initial:
            client.conn.sendall(struct.pack('?',False))
            return False
        client.conn.sendall(struct.pack('?',True))
        self.members[client.user_id] = client
        member_and_topics = [[(cli,self.members[cli].name) for cli in self.members]]
        member_and_topics.append(all_topics)
        member_and_topics = pickle.dumps(member_and_topics)
        send_msg(client.conn,member_and_topics,Group.headers.NewAddition)
        return True

    def run(self):
        while True:
            if self.state == self.States.Terminated:
                break
            for member in list(self.members):
                try:
                    message_type = self.members[member].conn.recv(4)
                    if not message_type:
                        break
                    message_type = struct.unpack('i',message_type)[0]
                    message = recv_msg(self.members[member].conn)
                    self.handle_messages[Group.headers(message_type)](member,message)
                except BlockingIOError:
                    pass
            time.sleep(0.2)


    def BroadCast(self,sender,msg):
        for each in self.members:
            if each != sender:
                send_msg(self.members[each].conn,struct.pack('i',sender)+msg,Group.headers.BroadCastMessage)
    
    def SelectTopic(self,sender,msg):
        if self.state == self.States.initial:
            msg = pickle.loads(msg)
            if msg in all_topics:
                self.state = self.States.questioned
                self.TopicSelected = msg
                cursor.execute("select * from Questions where Topic = '{0}' order by rand() limit 1".format(self.TopicSelected))
                Question_Data = cursor.fetchall()[0]
                self.Question = Question_Data
                qtype = Question_Data[3]
                if(qtype):
                    Question = Question_Data[2]
                    Options = [Question_Data[4],Question_Data[5],Question_Data[6],Question_Data[7]]
                    Question_payload = {"Topic":self.TopicSelected,"Question":Question,"Options":Options,"qtype":True}
                else:
                    Question = Question_Data[2]
                    Question_payload = {"Topic":self.TopicSelected,"Question":Question,"qtype":False}
                for each in self.members:
                    send_msg(self.members[each].conn,struct.pack('i',sender)+pickle.dumps(Question_payload),Group.headers.Question)
    
    def PersonalMessage(self,sender,msg):
        reciever = msg[:4]
        reciever = struct.unpack('i',reciever)[0]
        msg = msg[4:]
        send_msg( self.members[reciever].conn,struct.pack('i',sender)+msg,Group.headers.PersonalMessage)

    def CheckAnswer(self,sender,msg):
        if self.state == self.States.questioned:
            AnswerSelected = pickle.loads(msg)
            CorrectAnswer = self.Question[8]
            Explanation = self.Question[9]
            result = False
            if AnswerSelected == CorrectAnswer:
                result = True
            self.state = self.States.Answered
            for each in self.members:
                send_msg(self.members[each].conn,struct.pack('i',sender)+pickle.dumps([AnswerSelected,CorrectAnswer,result,Explanation]),Group.headers.FinalAnswer)
    
    def NextStep(self,sender,msg):
        if self.state == self.States.Answered:
            msg = pickle.loads(msg)
            if msg == "q":
                self.members[sender].conn.close()
                self.members.pop(sender)
                if not self.members:
                    self.state = self.States.Terminated
            elif msg == 'r':
                self.members[sender].conn.setblocking(True)
                CliThread = Thread(target = convert,args=(self.members[sender],))
                CliThread.start()
                self.members[sender].conn.sendall(struct.pack('????',False,False,False,False))
                self.members.pop(sender)
                if not self.members:
                    self.state = self.States.Terminated
            elif msg == 'n':
                self.ActiveMembers += 1
            if self.ActiveMembers == len(self.members) and self.ActiveMembers!=0:
                self.ActiveMembers = 0
                self.state  = self.States.initial
                member_and_topics = [[(cli,self.members[cli].name) for cli in self.members]]
                member_and_topics.append(all_topics)
                member_and_topics = pickle.dumps(member_and_topics)
                for each in self.members:
                    send_msg(self.members[each].conn,member_and_topics,Group.headers.NewAddition)


def convert(client):
    client.run()




cursor = db.cursor()
cursor.execute("Select Topic from Questions group by Topic")
all_topics = cursor.fetchall()
all_topics = [topic[0] for topic in all_topics]


def Individual(client):
    try:
        AllTopics = pickle.dumps(all_topics)
        client.conn.sendall(AllTopics)
        selected_topic = client.conn.recv(255).decode('utf-8')
        cursor.execute("select * from Questions where Topic = '{0}' order by rand() limit 1".format(selected_topic))
        Question_Data = cursor.fetchall()[0]
        qtype = Question_Data[3]
        if(qtype):
            Question = Question_Data[2]
            Options = [Question_Data[4],Question_Data[5],Question_Data[6],Question_Data[7]]
            Question_payload = {"Question":Question,"Options":Options}
            Question_payload = pickle.dumps(Question_payload)
            client.conn.sendall(Question_payload)
        else:
            Question = Question_Data[2]
            Question_payload = {"Question":Question}
            Question_payload = pickle.dumps(Question_payload)
            client.conn.sendall(Question_payload)
        AnsRecv = client.conn.recv(255).decode('utf-8')
        Correct_Ans = Question_Data[8]
        result = True
        Explanation = Question_Data[9]
        if AnsRecv != Correct_Ans:
            result = False
        comp_result = [result,Correct_Ans,Explanation]
        comp_result = pickle.dumps(comp_result)
        client.conn.sendall(comp_result)
        next = client.conn.recv(BUFFER_SIZE).decode('utf-8')
        if next == 'n':
            Individual(client)
        elif next == 'r':
            client.run()

    except Exception as e:
        print(e)



def CreateNewGroup(GroupID,client):
    newGroup = Group(GroupID,client)
    all_groups[GroupID] = newGroup
    newGroup.run()

class ClientObject():
    def __init__(self,ip,port,conn,UserID,name): 
        self.ip = ip 
        self.name = name
        self.port = port
        self.conn = conn
        self.user_id = UserID
        self.run = self.__run
        print( "New server socket thread started for " + ip + ":" + str(port) )
        
    def send(self,message):
        self.conn.sendall(message)
    
    def recv(self):
        data = recvall(self.conn)
        return data
    def __run(self): 
        try:
            mode = self.conn.recv(1024).decode('utf-8')
            if(mode == 'I'):
                Individual(self)
            elif(mode == 'G'):
                all_grps = list(all_groups.keys())
                all_grps = pickle.dumps(all_grps)
                self.conn.sendall(all_grps)
                GrpNo = self.conn.recv(BUFFER_SIZE)
                GrpNo = pickle.loads(GrpNo)
                global GroupID
                done = False
                while(GrpNo != 'new'):
                    GrpNo = int(GrpNo)
                    done = all_groups[GrpNo].AddMember(self)
                    if done:
                        break
                    GrpNo =pickle.loads(self.conn.recv(BUFFER_SIZE))
                self.conn.setblocking(False)
                if GrpNo == 'new':
                    newGrpNo = 0
                    try:
                        GroupIDLock.acquire()
                        newGrpNo = GroupID
                        GroupID += 1
                        GroupIDLock.release()
                        self.conn.sendall(struct.pack('?',True))
                        CreateNewGroup(newGrpNo,self)
                    except:
                        self.conn.sendall(struct.pack('?',False))
                        pass
                    

        except Exception as e:
            print(e)


def setupClient(ip,port,userID,conn):
    name =pickle.loads(conn.recv(1024))
    conn.send((userID).to_bytes(2,"little"))
    newClient = ClientObject(ip,port,conn,userID,name)
    newClient.run()
    #newClient.join()


try:
    my_socket = socket.socket()     # Create a socket object
    my_host = socket.gethostname()
    my_port = 5034# Store a port for your service.
#    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    my_socket.bind((my_host, my_port))
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)    
    my_socket.listen(5)
    print("Listening for new Connections")
except Exception as e:
    print(e)
Threads = []

while True:
    try:
        cl, myaddr = my_socket.accept()     # Establish connection with client.
        clientIP,clientPort = myaddr[0],myaddr[1]
        UserID +=1
        newThread = Thread(target=setupClient,args = (clientIP,clientPort,UserID,cl,))
        newThread.setDaemon(True)
        Threads.append(newThread)
       # time.sleep(0.5)
        newThread.start()
    except KeyboardInterrupt:
        exit(1)

for t in Threads:
    t.join()

my_socket.close()



