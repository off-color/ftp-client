import exceptions as exc
import re
import socket
import os
import help
import contextlib
import progress


TIMEOUT = 10
ENCODING = 'utf-8'
END_OF_COMMAND = '\r\n'
DEBUG = False
IS_ACTIVE = False
ERROR_PATTERN = re.compile(r'[4|5].*')


class Client:
    def __init__(self):
        self.UNDEMANDING_COMMANDS = {'exit', 'quit', 'reconnect', 'help'}

        self.commands = {
            'ls': self.ls,
            'cd': self.cd,
            'get': self.get,
            'reconnect': self.reconnect,
            'close': self.close,
            'exit': self.exit,
            'quit': self.exit,
            'help': self.help,
            'send': self.send}

        self._adjust()

    def _adjust(self, needToReconnect=False):
        '''update client state after disconnecting or for first usage'''
        self.isConnected = False
        self.timeToExit = False
        self.sock = socket.socket()
        self.sock.settimeout(TIMEOUT)

        if needToReconnect:
            print(self.connect(self.hostName, self.port))
            return self.login(self._userName, self._password)

    def _setup_connection(self, host, port):
        '''configure client at connection'''
        try:
            self.sock.connect((host, port))
        except socket.timeout:
            self._disconnect()
            raise

        self.isConnected = True
        self.hostName = host
        self.port = port

    def enter_pasv(self):
        '''enter passive mode'''
        resp = self.send_cmd('PASV')
        searchResult = re.match(r'.*\(((?:\d+,){5}\d+)\)', resp)
        if not searchResult:
            raise exc.FailedOperationException(resp)

        data = searchResult.group(1).split(',')
        dataHost = '.'.join(data[:4])
        dataPort = int(data[4]) * 2**8 + int(data[5])

        sock = socket.socket()
        sock.connect((dataHost, dataPort))
        sock.settimeout(TIMEOUT)
        return sock

    def enter_active_mode(self):
        '''enter active mode'''
        self.dataSock = socket.socket()
        self.dataSock.settimeout(TIMEOUT)
        self.dataSock.bind(('', 0))
        self.dataSock.listen(1)

        host = self.sock.getsockname()[0].replace('.', ',') + ','
        port = self.dataSock.getsockname()[1]
        port = '{},{}'.format(port // 256, port % 256)
        portArgs = host + port

        self.send_cmd('PORT', portArgs)
        return self.dataSock

    def _disconnect(self, needToReconnect=False):
        '''close connection'''
        self.sock.close()
        return self._adjust(needToReconnect)

    def _prepare_before_get_data(self, cmd, *params):
        '''enter mode and send command'''
        cmd = ' '.join((cmd, *params)) + END_OF_COMMAND

        if IS_ACTIVE:
            sock = self.enter_active_mode()
        else:
            sock = self.enter_pasv()

        self.sock.sendall(cmd.encode(ENCODING))
        resp = get_resp(self.sock)
        if ERROR_PATTERN.match(resp):
            raise exc.FailedOperationException(resp)
        self._lastResp = resp

        if IS_ACTIVE:
            conn, addr = sock.accept()
            sock = conn
        return sock

    def send_cmd(self, cmd, *params):
        '''send a command to remote server and return resp'''
        cmd = ' '.join((cmd, *params)) + END_OF_COMMAND

        try:
            self.sock.sendall(cmd.encode(ENCODING))
            resp = get_resp(self.sock)
        except socket.timeout:
            self._disconnect()
            raise

        if resp.startswith('421'):
            self._disconnect()
            raise exc.TimeoutException(resp)
        return resp

    def connect(self, host='', port=21, *args):
        '''connect to remote ftp'''
        if self.isConnected:
            raise exc.NotConnectedException(
                      'Already connected to {},'
                      'use close first.'.format(self.hostName))

        self._setup_connection(host, port)
        resp = get_resp(self.sock)

        if resp.startswith('421'):
            self._disconnect()
            raise exc.TimeoutException(resp)
        return resp

    def _user(self, name):
        '''send new user information'''
        return self.send_cmd('USER', name)

    def _passw(self, password):
        '''send new password information'''
        return self.send_cmd('PASS', password)

    def login(self, name, password, *args):
        '''relogin on remote ftp'''
        resp = self._user(name)
        if resp.startswith('421'):
            raise exc.TimeoutException(resp)

        resp = self._passw(password)
        if resp.startswith('530'):
            raise exc.FailedOperationException(resp)

        self._userName = name
        self._password = password
        return resp

    def ls(self, directoryName='', *args):
        '''list contents of remote directory'''
        sock = self._prepare_before_get_data('LIST', directoryName)

        with sock:
            if DEBUG:
                print(self._lastResp)
            for line in sock.makefile(encoding=ENCODING):
                print(line[:-1])

        return get_resp(self.sock)

    def cd(self, directoryName='', *args):
        '''change remote working directory'''
        return self.send_cmd('CWD', directoryName)

    def get(self, remoteFile='', localFile='', *args):
        '''receive file'''
        localFile = localFile or remoteFile
        localFile = os.path.expanduser(localFile)
        resp = self.cd(remoteFile)
        if not resp.startswith('5'):
            self.cd('..')
            return self._get_dir(remoteFile, localFile)
        if os.path.isdir(localFile):
            raise exc.FailedOperationException(
                  'Second argument must be file, not directory')

        self.send_cmd('TYPE I')
        size = self.size(remoteFile)
        sock = self._prepare_before_get_data('RETR', remoteFile)
        try:
            with sock, open(localFile, 'wb') as f:
                bar = progress.Progress(size)
                if DEBUG:
                    print(self._lastResp)
                for line in sock.makefile('rb'):
                    bar.update(len(line))
                    f.write(line)
        except Exception as e:
            with contextlib.suppress(FileNotFoundError):
                os.remove(localFile)
            if not isinstance(e, exc.FailedOperationException):
                get_resp(self.sock)
            raise
        else:
            return get_resp(self.sock)

    def _nlst(self, *args):
        '''get list of files'''
        sock = self._prepare_before_get_data('NLST')
        with sock:
            result = [line[:-1] for line in sock.makefile(encoding=ENCODING)]
        get_resp(self.sock)
        return result

    def _get_dir(self, directoryName, localDirectory, *args):
        '''receive directory'''
        localDirectory = localDirectory or directoryName
        if not os.path.isdir(localDirectory):
            os.mkdir(localDirectory)
        resp = self.cd(directoryName)
        os.chdir(localDirectory)

        for note in self._nlst():
            resp = self.get(os.path.basename(note))

        self.cd('..')
        os.chdir('..')
        return resp

    def close(self, *args):
        '''terminate ftp session'''
        resp = self.send_cmd('QUIT')
        self._disconnect()
        return resp

    def exit(self, *args):
        '''terminate ftp session and exit'''
        try:
            if self.isConnected:
                return self.close()
        finally:
            self.timeToExit = True
        return ''

    def reconnect(self, *args):
        '''reconnect to remote server'''
        if self.isConnected:
            return self._disconnect(True)
        else:
            return self._adjust(True)

    def help(self, command='', *args):
        '''print local help information'''
        if not command:
            titles = sorted(self.commands)
            help_str = '  '.join(titles)
            help_str = '{:<75}\n'.format(help_str)
        else:
            if command not in self.commands:
                raise exc.FailedOperationException(
                    '?Invalid help command ' + command)
            help_str = help.help[command]
        return help_str

    def send(self, localFile='', remoteFile='', *args):
        '''send file'''
        remoteFile = remoteFile or localFile
        localFile = os.path.expanduser(localFile)
        if os.path.isdir(localFile):
            return self._send_dir(localFile, remoteFile)
        if not os.path.isfile(localFile):
            raise exc.FailedOperationException('Local file not found')

        self.send_cmd('TYPE I')
        sock = self._prepare_before_get_data('STOR', remoteFile)
        with sock, open(localFile, 'rb') as f:
            if DEBUG:
                print(self._lastResp)
            for line in f:
                sock.sendall(line)

        return get_resp(self.sock)

    def _send_dir(self, localDir, remoteDir, *args):
        '''send directory'''
        resp = self.cd(remoteDir)
        if resp.startswith('5'):
            if remoteDir not in self._nlst():
                resp = self.mkdir(remoteDir)
                if resp.startswith('5'):
                    raise exc.FailedOperationException(resp)
                self.cd(remoteDir)
            else:
                raise exc.FailedOperationException(
                      'Could not create directory')

        for root, dirs, files in os.walk(localDir):
            os.chdir(localDir)
            for f in files:
                resp = self.send(f)
            for d in dirs:
                resp = self._send_dir(d, d)
            os.chdir('..')
            break
        self.cd('..')
        return resp

    def mkdir(self, dirName, *args):
        '''make a directory on remote machine'''
        return self.send_cmd('MKD', dirName)

    def size(self, fileName, *args):
        '''get size of file'''
        return self.send_cmd('SIZE', fileName)


def get_resp(sock):
    '''get resp form the socket'''
    data = b''

    while True:
        dataPoint = sock.recv(4096)
        data += dataPoint
        strings = dataPoint.decode(ENCODING).split('\n')
        if len(strings) < 2 or re.match(r'^\d{3} .*', strings[-2]):
            break

    return data.decode(ENCODING)
