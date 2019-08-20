import unittest
import socket
from unittest.mock import patch, mock_open, call
import ftp
import fakeserver as fk
import contextlib
import io
import progress


class Tests(unittest.TestCase):
    @patch('socket.socket', autospec=True)
    def setUp(self, mockSock):
        self.serv = fk.FakeServer('MyAddress', mockSock)
        mockSock().connect.side_effect = self.serv.connect
        mockSock().send.side_effect = self.serv.send
        mockSock().sendall.side_effect = self.serv.send
        self.client = ftp.Client()

    def test_default_client_values(self):
        self.assertFalse(self.client.isConnected)
        self.assertFalse(self.client.timeToExit)
        self.assertIsInstance(self.client.sock, socket.socket)
        self.client.sock.settimeout.assert_called_once_with(ftp.TIMEOUT)

    def test_connect(self):
        result = self.client.connect('MyAddress')
        self.assertEqual(result, '220 smth\r\n')
        self.assertTrue(self.client.isConnected)
        self.assertEqual(self.client.hostName, 'MyAddress')
        self.assertEqual(self.client.port, 21)

    @patch('socket.socket', autospec=True)
    def test_list_of_files(self, mockObject):
        self.serv.dataMock = mockObject
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = self.client.ls()
        string = f.getvalue()
        self.assertEqual(result, '226 Directory send OK.\r\n')
        self.assertEqual(string, 'file1\nfile2\nfile3\n')

    @patch('progress.Progress', autospec=True)
    @patch('socket.socket', autospec=True)
    def test_get_file(self, mockObject, mockBar):
        self.serv.dataMock = mockObject
        mockOpen = mock_open()
        with patch('builtins.open', mockOpen, create=True):
            result = self.client.get('file1')
        self.assertEqual(result, '226 Transfer complete.\r\n')
        mockOpen().write.assert_called_once_with(b'file1data')

    @patch('os.path', autospec=True)
    @patch('socket.socket', autospec=True)
    def test_send_file(self, mockObject, mockPath):
        mockPath.isdir.return_value = False
        self.serv.dataMock = mockObject

        with patch('builtins.open', mock_open(read_data=b'file4data'),
                   create=True) as m:
            m.return_value.__iter__.return_value = iter([b'file4data'])
            result = self.client.send('file4')

        self.assertEqual(result, '226 Transfer complete.\r\n')
        self.assertTrue(b'file4' in self.serv.files)
        self.assertEqual(b'file4data', self.serv.data[b'file4'])

    def test_not_connected(self):
        self.client.connect('MyAddress')
        with self.assertRaises(Exception):
            self.client.connect('AnotherAddr')

    @patch('socket.socket', autospec=True)
    def test_timeout_connect(self, mockObject):
        self.serv.mockSock().connect.side_effect = socket.timeout
        with self.assertRaises(socket.timeout):
            self.client.connect('MyAddress')
        self.serv.mockSock().close.assert_called_once_with()
        self.assertFalse(self.client.isConnected)

    def test_timeout_send(self):
        self.serv.mockSock().send.side_effect = socket.timeout
        self.serv.mockSock().sendall.side_effect = socket.timeout
        with self.assertRaises(socket.timeout) as e:
            self.client.send_cmd('smth')
        self.serv.mockSock().close.assert_called_once_with()
        self.assertFalse(self.client.isConnected)

    def test_login(self):
        self.client.connect('MyAddress')
        result = self.client.login('me', 'qwerty')
        self.assertEqual(result, '230 Login successful.\r\n')

    def test_login_incorrect(self):
        self.client.connect('MyAddress')
        with self.assertRaises(Exception):
            self.client.login('smth', 'smth')

    @patch('progress.Progress', autospec=True)
    @patch('os.chdir', autospec=True)
    @patch('os.mkdir', autospec=True)
    @patch('os.path', autospec=True)
    @patch('socket.socket', autospec=True)
    def test_get_dir(self, mockObject, mockOs, mockMkdir, mockChdir, mockBar):
        mockOs.basename.side_effect = lambda x: x
        mockOs.isdir.side_effect = lambda x: False
        mockOs.expanduser.side_effect = lambda x: x
        self.serv.dataMock = mockObject
        mockOpen = mock_open()

        with patch('builtins.open', mockOpen, create=True):
            result = self.client.get('mydir')

        self.assertEqual(result, '226 Transfer complete.\r\n')
        mockMkdir.assert_called_once_with('mydir')
        self.assertEqual(mockChdir.mock_calls, [call('mydir'), call('..')])
        self.assertEqual(mockOpen.call_args_list,
                         [call('myfile1', 'wb'), call('myfile2', 'wb')])
        self.assertEqual(mockOpen().write.mock_calls,
                         [call(b'myfile1data'), call(b'myfile2data')])

    @patch('os.chdir', autospec=True)
    @patch('os.walk', autospec=True)
    @patch('os.path', autospec=True)
    @patch('socket.socket', autospec=True)
    def test_send_dir(self, mockObject, mockOs, mockWalk, mockChdir):
        mockOs.expanduser.side_effect = lambda x: x
        mockOs.isdir.side_effect = lambda x: x == 'favdir'
        mockWalk.side_effect =\
            lambda x: [('favdir', [], ['myfile3', 'myfile4'])]
        self.serv.dataMock = mockObject
        mockOpen = mock_open(read_data=b'myfile3data')

        with patch('builtins.open', mockOpen,
                   create=True) as m:
            m.return_value.__iter__.side_effect =\
                lambda: iter([b'myfile3data'])
            result = self.client.send('favdir')

        self.assertEqual(result, '226 Transfer complete.\r\n')
        self.assertEqual(mockChdir.mock_calls, [call('favdir'), call('..')])
        self.assertEqual(mockOpen.call_args_list,
                         [call('myfile3', 'rb'), call('myfile4', 'rb')])
        self.assertEqual(
            self.serv.dirs[b'favdir'],
            ([b'myfile3', b'myfile4'],
             {b'myfile3': b'myfile3data', b'myfile4': b'myfile3data'}))

    @patch('socket.socket', autospec=True)
    def test_active_mode(self, mockObject):
        self.serv.mockSock().getsockname.return_value = ('127.0.0.1', 33319)
        mockObject().getsockname.return_value = ('127.0.0.1', 33319)
        result = self.client.enter_active_mode()
        mockObject().settimeout.assert_called()
        mockObject().bind.assert_called()
        mockObject().listen.assert_called_with(1)
        self.serv.mockSock().sendall.assert_called_with(
            b'PORT 127,0,0,1,130,39\r\n')

    @patch('socket.socket', autospec=True)
    def test_correct_exit(self, mockObject):
        self.client.connect('Myaddr')
        self.client.exit()
        self.serv.mockSock().sendall.assert_called_with(b'QUIT\r\n')
        self.serv.mockSock().close.assert_called_once_with()
        self.assertTrue(self.client.timeToExit)


if __name__ == '__main__':
    unittest.main()
