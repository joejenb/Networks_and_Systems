import socket
import pickle
import sys


# Sets the maximum size of the header to be 10 bytes meaning can have a message of up to 10^10 bytes
header_size = 10


def main():
    """ Gets the address of the server it would like to connect to as input, attempts to connect. If successful
    repeatedly asks the user what they would like to do, checks that their input is valid and if so executes their
    request."""
    server_socket = (sys.argv[1], int(sys.argv[2]))
    boards, run = view_boards(server_socket), True
    while run:
        usr_inp = display_menu()
        if usr_inp.isdigit():
            usr_inp = int(usr_inp)
            if usr_inp in range(1, len(boards)+1):
                view_messages(boards[int(usr_inp)-1], server_socket)
            else:
                print("Invalid Board Number Entered \n")
        else:
            if usr_inp == "POST":
                send_message(server_socket, boards)
            elif usr_inp == "QUIT":
                run = False
            else:
                print("Invalid Command Entered \n")


def view_messages(board_name, server_address):
    """ Responsible for formatting a 'GET_MESSAGES' request, then uses serialise_and_send to send this to the server.
    If successful it then formats the messages sent back by the server and prints them to the terminal for the user to
    see."""
    msg_obj = serialise_and_send(server_address, {'Command': "GET_MESSAGES", "Data": board_name})
    if msg_obj["Command"] == "OK":
        print("GET_MESSAGES command was successful\n")
        msg_dict = msg_obj["Data"]
        for each in msg_dict.keys():
            print(each + ':      ' + msg_dict[each])
        print("")
    else:
        print("ERROR:       " + msg_obj["Data"] + "\n")


def view_boards(new_socket):
    """ Responsible for formatting a 'GET_BOARDS' request, then uses serialise_and_send to send this to the server. If
    successful it then formats the boards sent back by the server and prints them to the terminal for the user to see.
    """
    board_obj = serialise_and_send(new_socket, {'Command': "GET_BOARDS"})
    if board_obj["Command"] == "OK":
        print("GET_BOARDS command was successful.\n")
        li_boards = board_obj["Data"]
        for i in range(len(li_boards)):
            print(str(i+1) + '.     ' + li_boards[i])
            print('')
        return li_boards
    print("ERROR:       " + board_obj["Data"] + "\n")
    sys.exit(1)


def send_message(server_address, boards):
    """ Responsible for taking user input that specifies what they would like to post and where, checking that the board
    number entered is valid. Next it formats the input in a dictionary that can then be passed to serialise_and_send.
    The success of the command is then printed to the screen.
    """
    invalid = True
    while invalid:
        msg_board = input("Please enter the board number you would like to post to: ")
        if msg_board.isdigit() and int(msg_board) in range(1, len(boards)+1):
            invalid = False
        else:
            print("Invalid Board Number Entered.")

    msg_title = input("Please enter a message title: ")
    msg = input("Please enter the message you would like to send: ")

    data = {'Command': "POST_MESSAGE", 'Board': boards[int(msg_board)-1], 'Name': msg_title, 'Message': msg}
    r_data = serialise_and_send(server_address, data)

    if r_data["Command"] == "ERROR":
        r_data["Data"] = "ERROR:       " + r_data["Data"]
    print("\n" + r_data["Data"] + "\n")


def display_menu():
    """ Prints a list of options for the user to the screen, then takes user input in the form of a string."""
    print("Please enter: ")
    print("     - A board number to view its 100 most recent messages")
    print("     - POST to send a message to a specific board")
    print("     - QUIT to close connections and end the program")
    usr_inp = input("Input:     ")
    print("\n")
    return usr_inp


def make_connection(server_address):
    """ Makes a socket object that uses IPv4 and the TCP protocol. Next tries to connect to the specified server. If
    successful then the max time that the client will wait for a server response is set to 10 seconds. If not successful
    then the reason is printed and the program exits."""
    new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        new_socket.connect(server_address)
        new_socket.settimeout(10)
        return new_socket
    except socket.error as err:
        print("Unable to connect to server. Error: \n" + str(err))
        sys.exit(1)


def serialise_and_send(server_address, data):
    """ This is a generic function used for all communication between the client and server that serialises the
    data, adds a header to it specifying the size of the message and then sends it to the server. It then listens for
    the response and returns this to the calling function.
    """
    new_socket = make_connection(server_address)
    pickle_data = pickle.dumps(data)
    to_send = bytes("{:<{header_size}}".format(len(pickle_data), header_size=header_size), 'utf-8') + pickle_data
    new_socket.send(to_send)
    s_data = listen(new_socket)
    return s_data


def listen(conn):
    """ Listens for any incoming data from the server. Upon receiving the first packet of a new message it notes the
     size of the whole expected message stated in the header. It then iterates until all of the expected data has
     arrived, at which point it is de-serialised and returned. If no data is received then this indicates that the
     server has closed its connection so the program exits."""
    p_msg, new, msg_size = b'', True, None
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                print("The server is no longer running")
                sys.exit(1)
            elif new:
                new, msg_size = False, int(data[:header_size])
            p_msg += data
            if len(p_msg) - header_size == msg_size:
                conn.close()
                return pickle.loads(p_msg[header_size:])
        except socket.timeout:
            print("ERROR:       Response not received within 10 seconds")
            sys.exit(1)


main()
