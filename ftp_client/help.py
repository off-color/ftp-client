help = {
        'ls': '{0} {1}\n\t'
        'Print a listing of the contents of a directory on the remote\n\t'
        'machine.  The listing includes any system-dependent informa‐\n\t'
        'tion that the server chooses to include. If {1} is\n\t'
        'left unspecified, the current working directory is used.\n'
        .format('ls', '[{0}]'.format('remote-directory')),


        'cd': '{0} {1}\n\t'
              'Change the working directory on the remote machine to\n\t'
              '{1}.\n'.format('cd',
                              'remote-directory'),

        'get':
        ('{0} {1} {2}\n\t'
         'Retrieve the remote-file and store it on the local machine.\n\t'
         'If the local file name is not specified, it is given the same\n\t'
         'name it has on the remote machine. {1} can be directory as well.\n\t'
         'If download target is directory, then all tree of subdirectories\n\t'
         'will be downloaded.\n').format('get',
                                         'remote-file',
                                         '[{0}]'.format(
                                                       'local-file')),

        'reconnect':
        '{0}\n\t'
        'Reconnect to remote server. It works even if you already\n\t'
        'disconnected from the remote server.\n'.format('reconnect'),


        'close': '{0}\n\t'
                 'Disconnect from remote server.\n'.format('close'),

        'exit': '{0}\n\t'
                'Terminate ftp session and exit.\n'.format('exit'),

        'quit': '{0}\n\t'
                'Terminate ftp session and exit.\n'.format('quit'),

        'help':
        ('{0} {1}\n\t'
         'Print local help information about command {1}.\n\t'
         'If {1} is left unspecified, program will print\n\t'
         'list of commands.\n')
        .format('help', '[{0}]'.format('command')),

        'send':
        '{0} {1} {2}\n\t'
        'Store a local file on the remote machine. If {2} is\n\t'
        'left unspecified, the local file name is used.\n\t'
        '{1} can be directory as well.\n\t'
        'If upload target is directory, then all tree of subdirectories\n\t'
        'will be uploaded.\n'
        .format('send', 'local-file',
                '[{0}]'.format('remote-file'))}
