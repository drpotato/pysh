#! /usr/bin/env python3

import os

__author__ = 'Chris Morgan'


class Pysh:
    """Pysh - The Python Shell

    TODO:
        run commands in history
        manage background processes
        piping
        intelligent prompt
        use arrow keys to navigate history
    """

    def __init__(self):
        self.history = [] # I want to move this to a class later.
        self.background_processes = [] # Wouldn't mind a class for this...
        self.prompt = "=> " # Maybe make this into a class also.

    def start(self):
        """starts the shell, listening until 'exit' is called
        """

        while True:
            input_string = input(self.prompt)

            # Lecturer will provide parsing for input string, but this will do
            # for now.
            input_list = input_string.split()
            programme, arguments = input_list[0], input_list[1:]
            if '&' in arguments:
                arguments.pop()
                background = True
            else:
                background = False

            # Switch statement for not-built in functionality.
            if programme == 'exit':
                # Break out of loop.
                break
            elif programme == 'cd':
                # Expand the path and change the shell's directory.
                real_path = os.path.expanduser(' '.join(arguments))
                os.chdir(real_path)
            else:
                # Run the command with arguments.
                current_command = Command(programme, arguments, background)
                current_command.run()
                self.history.append(current_command)


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

        # Slightly hacky, as the arguments need to contain the programme name.
        self.arguments = [programme] + arguments
        self.background = background

        # If the process runs in the background, we still need to return this.
        self.status = None

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
    shell = Pysh()
    shell.start()

if __name__ == '__main__':
    main()
