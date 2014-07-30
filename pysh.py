#! /usr/bin/env python3

import os


class Command:

    def __init__(self, programme, arguments=[], background=False):
        """constructor for command

        :param programme:   name of programme to be executed
        :type programme:    str or unicode
        :param arguments:   arguments for the programme
        :type arguments:    list(str, ...)
        :param background:  whether to run program or not
        :type background:   bool
        """
        self.programme = programme
        self.arguments = [programme] + arguments # Slightly hacky, as the arguments need to contain the programme name.
        self.background = background

    def run(self):
        """runs the command and manages the child process

        :returns:   returns child process id and exist status
        :rtype:     tuple(int, int)
        """
        # Fork the current process and store the child process id for later use.
        self.child = os.fork()

        if self.child == 0:
            # If this process is the child, replace current execution with programme to run.
            os.execvp(self.programme, self.arguments)

        if not self.background:
            # If the process is not going to run in the background, wait for the programme to finish.
            _, self.status = os.waitpid(self.child, 0)

        return self.child, self.status


def main():

    while True:

        # Grab user input and split it up into command and args.
        command_array = input('=> ').split()
        command  = Command(command_array[0], command_array[1:])

        # Switch statement to determine command behaviour.
        if command.programme == 'exit':
            break
        elif command.programme == 'cd':
            os.chdir(command.args[1])
        else:
            command.run()


if __name__ == '__main__':
    main()
