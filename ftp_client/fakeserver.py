class FakeServer:
    def __init__(self, addr, mockSock):
        self.mockSock = mockSock
        self.addr = addr

        self.cmds = {b'PASV': self.pasv,
                     b'LIST': self.ls,
                     b'RETR': self.retr,
                     b'CWD': self.cwd,
                     b'TYPE': self.type,
                     b'USER': self.enter_user,
                     b'PASS': self.enter_pass,
                     b'STOR': self.stor,
                     b'NLST': self.nlst,
                     b'MKD': self.mkdir,
                     b'PORT': self.port,
                     b'QUIT': self.quit,
                     b'SIZE': self.size}

        self.files = [b'file1', b'file2', b'file3']
        self.data = {b'file1': b'file1data', b'file2': b'file2data',
                     b'file3': b'file3data'}
        self.dataServ = None
        self.dataMock = None
        self.users = {b'me': b'qwerty'}
        self.user = ''
        self.parentServ = None
        self.dirs =\
            {b'mydir': ([b'myfile1', b'myfile2'],
                        {b'myfile1': b'myfile1data',
                         b'myfile2': b'myfile2data'})}
        self.currentDir = 'root'

    def connect(self, *args):
        if self.addr != 'dataServ':
            self.mockSock.return_value.recv.return_value = b'220 smth\r\n'

    def send(self, cmd):
        cmd = cmd[:-2]
        command, *args = cmd.split(b' ')
        self.cmds[command](*args)

    def pasv(self, *args):
        if self.dataServ is None:
            self.setup_data_server(self.dataMock, 'dataServ')
        self.mockSock.return_value.recv.return_value =\
            b'227 Entering Passive Mode (212,193,68,227,195,139)\r\n'

    def ls(self, *args):
        self.dataServ.data = b'\n'.join(self.files) + b'\n'
        self.mockSock.return_value.recv.return_value =\
            b'226 Directory send OK.\r\n'

    def retr(self, name):
        if name not in self.files:
            self.mockSock.return_value.recv.return_value =\
                b'550 No such file or directory\r\n'
        else:
            self.dataServ.data = self.data[name]
            self.mockSock.return_value.recv.return_value =\
                b'226 Transfer complete.\r\n'

    def cwd(self, dirName):
        if dirName not in self.dirs and dirName != b'..':
            self.mockSock.return_value.recv.return_value =\
                b'550 No such file or directory\r\n'
        elif dirName == b'..':
            self.dirs = {self.currentDir: (self.files, self.data)}
        else:
            self.files = self.dirs[dirName][0]
            self.data = self.dirs[dirName][1]
            self.dirs = {}
            self.currentDir = dirName
            self.mockSock.return_value.recv.return_value =\
                b'250 Successful changed.\r\n'

    def type(self, *args):
        self.mockSock.return_value.recv.return_value = b'250 \r\n'

    def setup_data_server(self, mockObject, name):
        self.dataServ = FakeServer(name, mockObject)
        self.dataServ.parentServ = self

        mockObject().connect.side_effect = self.dataServ.connect
        mockObject().send.side_effect = self.dataServ.send_data
        mockObject().sendall.side_effect = self.dataServ.send_all_data
        mockObject().recv.side_effect = self.dataServ.recv_data
        mockObject().makefile.side_effect = self.dataServ.recv_data_list
        return mockObject

    def send_data(self, data):
        self.data += data

    def send_all_data(self, data):
        self.data = data
        self.parentServ.data[self.parentServ.files[-1]] = data

    def recv_data(self, *args, **kwargs):
        return self.data

    def recv_data_list(self, *args, encoding=None):
        if encoding is not None:
            if isinstance(self.data, list):
                self.data = [x.decode() + '\n' for x in self.data]
                return self.data

            self.data = self.data.decode(encoding)
        return [self.data]

    def enter_user(self, name):
        self.user = name
        self.mockSock().recv.return_value =\
            b'331 Please specify the password.\r\n'

    def enter_pass(self, passw):
        if self.user in self.users and self.users[self.user] == passw:
            self.mockSock().recv.return_value = b'230 Login successful.\r\n'
        else:
            self.mockSock().recv.return_value = b'530 Login incorrect.\r\n'

    def stor(self, name):
        self.files.append(name)
        self.data[name] = self.dataServ.data
        self.mockSock().recv.return_value = b'226 Transfer complete.\r\n'

    def nlst(self, *args):
        self.dataServ.data = self.files

    def mkdir(self, dirName):
        if dirName in self.dirs:
            self.mockSock().recv.return_value =\
                b'550 Create directory operation failed.\r\n'
        else:
            self.dirs[dirName] = ([], {})

    def port(self, *args):
        self.mockSock.return_value.recv.return_value = b'250 \r\n'

    def quit(self, *args):
        pass

    def size(self, name):
        self.mockSock.return_value.recv.return_value = b'213 20\r\n'
