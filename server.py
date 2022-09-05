import socket
import threading
import pickle
import sys
import os
import logging
from datetime import datetime

# Sets the maximum size for a packet header to be 10 bytes, configures the logging file and creates a thread lock
header_size = 10
logging.basicConfig(filename='server.log', level=logging.INFO, format='%(message)s')
lock = threading.Lock()


class Server:
    def __init__(self, server_ip, port):
        """ Creates necessary properties for the server to operate including the address that it will run on, a server
        socket and a dictionary of connected clients."""
        self.ip = server_ip
        self.port = port
        self.connection_address = (self.ip, self.port)
        self.l_socket = None
        self.conns = {}
        self.run = True

    @property
    def run(self):
        """ Returns the property _run of the server object"""
        return self._run

    @run.setter
    def run(self, run):
        """ Sets the property _run of the server to either True or False"""
        if type(run) is bool:
            self._run = run

    def make_socket(self):
        """ Makes a socket object that uses IPv4 and the TCP protocol. Next tries to bind the socket to a port and
        network interface, if successful the socket is told to queue up to 5 messages. If not successful then the
        reason is printed and the program exits. To ensure that the socket does not block any keyboard interrupts when
        listening for a client connection its set to timeout after 1 second."""
        self.l_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.l_socket.bind(self.connection_address)
            self.l_socket.listen(5)
            self.l_socket.settimeout(1)
        except socket.error as err:
            print("Unable to bind to port. Error: \n" + str(err))
            os._exit(1)

    def listen_out(self):
        """ Server socket listens out for clients that are trying to connect, if a connection is successful then it
        is stored in a dictionary of client connections by the server. If the socket times out then return to main
        function where it can be checked for keyboard interrupts."""
        try:
            conn, client_address = self.l_socket.accept()
            self.conns[client_address] = conn
            return conn, client_address
        except socket.timeout:
            return False, False

    def log(self, client_address, command, success):
        """ Whenever there is any interaction between the server and a client the details surrounding it are documented
        in a log file by the server."""
        time = datetime.now().strftime("%a %d %b %H:%M:%S %Y")
        info = client_address[0] + ':' + str(client_address[1]) + '       ' + time + '       ' + command + '        ' + success
        logging.info(info)

    def send_data(self, conn, command, data):
        """ A method used by the server whenever it wants to send data to a client. It does so by storing the command
        and data in a dictionary that is then serialised and added to the end of a header stating the size of the
        serialised data."""
        s_data = {'Command': command, "Data": data}
        pickle_data = pickle.dumps(s_data)

        to_send = bytes("{:<{header_size}}".format(len(pickle_data), header_size=header_size), 'utf-8') + pickle_data
        conn.send(to_send)

    def get_data(self, conn):
        """ Upon receiving the first packet of a new message it notes the size of the whole expected message stated in
        the header. It then iterates until all of the expected data has arrived, at which point it is de-serialised and
        returned. If no data is received then this indicates that the client has closed its connection."""
        p_msg, new, msg_size = b'', True, None
        while len(p_msg) - header_size != msg_size:
            data = conn.recv(1024)
            if not data:
                return False
            elif new:
                new, msg_size = False, int(data[:header_size])
            p_msg += data
        return pickle.loads(p_msg[header_size:])

    def client_disconnect(self, client_address):
        """ A method used to close a specified client connection and then remove it from the servers dictionary of
        connected clients."""
        self.conns[client_address].close()
        del self.conns[client_address]

    def shut_down(self):
        """ Closes every connection between the server and any of its connected clients and then exits the program"""
        for each in list(self.conns.keys()):
            self.client_disconnect(each)
        self.l_socket.close()
        os._exit(1)


def handle_client(conn, client_address, server):
    """ Iterates until the client disconnects. First it waits for data sent by the client, then it reads which command
    the client has requested and attempts to execute it, logging its success afterwords. The success of the command
    and any relevant data is then sent in response to the client. If at any point the board folder is found to have been
    deleted or it is empty then the run property of the server is set to false and the thread dies."""
    while server.run:
        req_obj = server.get_data(conn)
        if not req_obj:
            server.client_disconnect(client_address)
            break
        command = req_obj["Command"]
        lock.acquire()
        res = check_for_boards(server)
        if res:
            server.run = False
        else:
            if command == "GET_BOARDS":
                msg, res = [name.replace('_', ' ') for name in os.listdir('board')], "OK"
            elif command == "GET_MESSAGES":
                res, msg = load_messages(req_obj)
            elif command == "POST_MESSAGE":
                res, msg = new_message(req_obj)
            else:
                res, msg = "ERROR", "Invalid command"
            server.send_data(conn, res, msg)
        server.log(client_address, command, res)
        lock.release()


def check_for_boards(server):
    """ Checks to see if the 'board' folder has been made and if so if it contains any message boards. If not then the
    "Error" is returned to the calling function, leading to the server being shutdown."""
    contents = os.listdir()
    if 'board' in contents:
        boards = [name.replace('_', ' ') for name in os.listdir('board')]
        if boards:
            return False
        else:
            print("ERROR:      No message boards have been defined " )
            return "ERROR"
    else:
        print("ERROR:       Folder 'board' has not been defined ")
        return "ERROR"


def new_message(msg_obj):
    """ Uses object sent by client to post their message to a requested message board. Provided there are no errors,
    this message will be stored in a file of its own within a folder of the specified board name."""
    params, c_params = list(msg_obj.keys()), ["Command", "Board", "Name", "Message"]
    missing = list(set(c_params)-set(params))
    if not missing:
        board = msg_obj["Board"].replace(' ', '_')
        if board in os.listdir('board'):
            msg_title = msg_obj["Name"].replace(' ', '_')
            file_name, msg = datetime.now().strftime("%Y%m%d-%H%M%S") + '-' + msg_title, msg_obj["Message"]
            file_obj = open(os.path.join('board', board, file_name)+'.txt', 'w')
            file_obj.write(msg)
            file_obj.close()
            return "OK", "New message posted successfully"
        return "ERROR", "Specified board does not exist"
    return "ERROR", "Missing parameter(s):      " + ', '.join(missing)


def load_messages(msg_obj):
    """ Takes a specific board name, orders the messages by date/time, loads the 100 most recent messages and then
    returns these messages and their corresponding titles formatted in a dictionary."""
    if "Data" in list(msg_obj.keys()):
        board_name = msg_obj["Data"].replace(' ', '_')

        if board_name in os.listdir('board'):
            board = os.path.join('board', board_name)
            total, messages = os.listdir(board), {}
            total.sort(key=date_value, reverse=True)
            recent = total[:100]

            for file_name in recent:
                msg_title = file_name.split('-')[2].split('.')[0].replace('_', ' ')
                file_obj = open(os.path.join(board, file_name), 'r')
                messages[msg_title] = file_obj.read()
                file_obj.close()

            return "OK", messages
        return "ERROR", "Specified board does not exist"
    return "ERROR", "Missing parameter(s):      Data"


def date_value(file_name):
    """A function used to calculate a value based on the name of a file. This value is what is then used to sort the
     files by creation time in the load_messages function."""
    file_list = file_name.split('-')
    date_string = file_list[0] + file_list[1]
    return int(date_string)


def main():
    """Responsible for instantiating a server object and then running it on the input address. It then iterates
    indefinitely, listening for connecting clients until server.run is False. When a new client connects all
    communication with that client is then handled by a separate thread."""
    print("Enter Ctrl+c to kill the server and end the program")
    server_ip, port = sys.argv[1], int(sys.argv[2])
    server, threads = Server(server_ip, port), []
    server.make_socket()
    while server.run:
        try:
            conn, client_address = server.listen_out()
            if conn and client_address:
                threads.append(threading.Thread(target=handle_client, args=(conn, client_address, server), daemon=True))
                threads[-1].start()
        except KeyboardInterrupt:
            server.run = False
    server.shut_down()


main()
