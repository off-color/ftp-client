from progressbar import Percentage, ProgressBar, FileTransferSpeed, ETA


class Progress:
    def __init__(self, size):
        self.size = int(size.split(' ')[-1])
        p_format = '%(percentage)3d%%    '
        self.pbar =\
            ProgressBar(widgets=[Percentage(format=p_format),
                                 ETA(), FileTransferSpeed()],
                        max_value=self.size)
        self.counter = 0
        # self.pbar.start()

    def update(self, length):
        self.counter += length
        updateValue = self.counter

        if updateValue >= self.size:
            self.pbar.finish()
        else:
            self.pbar.update(updateValue)
        print(end='\r')
