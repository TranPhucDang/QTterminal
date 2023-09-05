from qterminal.mux import mux
from qterminal.screen import QTerminalScreen
from qterminal.stream import QTerminalStream
from paramiko import AuthenticationException, SSHException, ChannelException, SSHClient,AutoAddPolicy
import threading
import time
import uuid
import re


class BaseBackend(object):

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.screen = QTerminalScreen(width, height, history=9999, ratio=.3)
        self.stream = QTerminalStream(self.screen)
        self.id = str(uuid.uuid4())

    def write_to_screen(self, data):
        self.stream.feed(data)

    def read(self):
        pass

    def resize(self, width, height):
        self.width = width
        self.height = height
        self.screen.resize(columns=width, lines=height)

    def connect(self):
        pass

    def get_read_wait(self):
        pass

    def cursor(self):
        return self.screen.cursor

    def close(self):
        pass


class PtyBackend(BaseBackend):
    pass


class SSHBackend(BaseBackend):

    def __init__(self, width, height, ip, username=None, password=None):
        super(SSHBackend, self).__init__(width, height)
        self.ip = ip
        self.username = username
        self.password = password
        self.authSusscess = 0  ### 1 is Successfully Authenticated, 0 is uthentication Failed, other Connection Error
        self.ssh_client = self.authentication()
        self.thread = threading.Thread(target=self.connect, args=(self.ssh_client,))
        self.ssh_client = None
        self.channel = None
        
        self.thread.start()

    # def connect1(self):
    #     self.ssh_client = SSHClient()
    #     self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
    #     try:
    #         self.ssh_client.connect(self.ip, username=self.username, password=self.password)
    #         self.channel = self.ssh_client.get_transport().open_session()
    #         self.channel.get_pty(width=self.width, height=self.height)
    #         self.channel.invoke_shell()
    #         self.authSusscess = 1
    #         timeout = 60
    #         while not self.channel.recv_ready() and timeout > 0:
    #             time.sleep(1)
    #             timeout -= 1

    #         self.channel.resize_pty(width=self.width, height=self.height)

    #         mux.add_backend(self)
    #     except (AuthenticationException, SSHException,
    #             ChannelException) as ex:
    #         self.authSusscess = 0
    #         print(f"{self.username}@{self.ip} {ex}")
    
    def connect(self, ssh_client):
        if self.authSusscess == 1:
            self.ssh_client = ssh_client
            self.channel = self.ssh_client.get_transport().open_session()
            self.channel.get_pty(width=self.width, height=self.height)
            self.channel.invoke_shell()
            timeout = 60
            while not self.channel.recv_ready() and timeout > 0:
                time.sleep(1)
                timeout -= 1

            # self.channel.resize_pty(width=self.width, height=self.height)

            mux.add_backend(self)
        else:
           pass
    
    def authentication(self):
        ssh_client = SSHClient()
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh_name = f"{self.username}@{self.ip}"
        try:
            ssh_client.connect(self.ip, username=self.username, password=self.password)
            self.authSusscess = 1
            return ssh_client
        except (AuthenticationException, SSHException,
                ChannelException) as ex:
            self.authSusscess = 0
            print(f"{self.username}@{self.ip} {ex}")
        

    def get_read_wait(self):
        return self.channel

    def write(self, data):
        self.channel.send(data)

    def read(self):
        output = self.channel.recv(1024)
        ssh_name = self.ssh_name.encode()
        regex_ssh_name = re.search(ssh_name, output, re.IGNORECASE)
        if regex_ssh_name is not None:
            rich_ssh_name = b'\x1b[01;32m'+ssh_name
            rich_start = regex_ssh_name.span()[0]
            rich_end = regex_ssh_name.span()[0]
            path = re.findall(r"\:(.*?)\$",str(output[rich_end:]))[0]
            output = output[:rich_start]+rich_ssh_name+b'\x1b[0m'+b':'+b'\x1b[01;34m'+path.encode()+b'\x1b[0m'+b'$ '

        self.write_to_screen(output)

    def resize(self, width, height):
        
        if self.channel:
            self.channel.resize_pty(width=width, height=height)
        super(SSHBackend, self).resize(width, height)

    def close(self):
        self.ssh_client.close()
        mux.remove_and_close(self)
