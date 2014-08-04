#! /usr/bin/env python3

import os
import sys

__author__ = 'Chris Morgan'


class Pysh:
    """
    Pysh - The Python Shell

    TODO:
        manage background processes
        piping
        error handling
        intelligent prompt
        use arrow keys to navigate history
    """

    __built_in_commands = ('h', 'history', 'cd', 'pwd', 'exit')

    def __init__(self):
        """
        Initialises the Pysh instance.
        """
        self.history = History()
        self.background_processes = [] # Wouldn't mind a class for this...
        self.prompt = "=> " # Maybe make this into a class also.

    def start(self):
        """
        Starts the shell, listening until 'exit' is called.
        """

        while True:
            input_string = input(self.prompt)

            # For future reference:
            # sub_commands = [list(sub_list) for seperator, sub_list in sys.groupby(command_list, lambda command:command=='|') if not seperator]

            # Lecturer will provide parsing for input string, but this will do
            # for now.
            input_list = input_string.split()
            programme, arguments = input_list[0], input_list[1:]
            if '&' in arguments:
                arguments.pop()
                background = True
            else:
                background = False

            # Check for built in functionality.
            if programme in self.__built_in_commands:
                command = BuiltInCommand(programme, arguments, background)
                if command.run():
                    self.history.append(command)

            else:
                # Run the command with arguments.
                command = Command(programme, arguments, background)
                command.run()
                self.history.append(command)

    def print_history(self):
        for index, item in enumerate(self.history):
            print("[%i]:\t%s" % (index, str(item)))


class Command:

    def __init__(self, programme, arguments=list(), background=False,
                 read=sys.stdin.fileno(), write=sys.stdout.fileno()):
        """
        Initialises a Command instance.

        :param programme:   name of programme to be executed
        :type programme:    str or unicode
        :param arguments:   arguments for the programme
        :type arguments:    list([str, ...])
        :param background:  whether to run program or not
        :type background:   bool
        """
        self.programme = programme

        # Slightly hacky, as the arguments need to contain the programme name.
        self.arguments = [programme] + arguments
        self.background = background

        # Set the input output pipes up.
        self.read = read
        self.write = write

    def run(self):
        """
        Runs the command and manages the child process.

        :returns:   returns child process id and exist status
        :rtype:     tuple(int, int)
        """
        # Fork the current process and store the child process id for later
        # use.
        child = os.fork()

        # If the process runs in the background, we still need to return this.
        status = None

        if child == 0:
            # If this process is the child, replace current execution with
            # programme to run.

            # Set up input/output.
            os.dup2(self.read, sys.stdin.fileno())
            os.dup2(self.write, sys.stdout.fileno())

            if self.read != sys.stdin.fileno():
                os.close(self.read)
            if self.write != sys.stdout.fileno():
                os.close(self.write)

            os.execvp(self.programme, self.arguments)

        if not self.background:
            # If the process is not going to run in the background, wait for
            # the programme to finish.
            _, status = os.waitpid(child, 0)

        return child, status

    def __str__(self):
        if self.background:
            ampersand = '&'
        else:
            ampersand = ''

        return ' '.join(self.arguments + [ampersand])


class BuiltInCommand(Command):

    def run(self):
        """
        Run the built in command.
        """
        if self.programme == 'exit':
            # Break out of loop.
            exit()

        elif self.programme == 'cd':
            # Expand the path and change the shell's directory.
            real_path = os.path.expanduser(' '.join(self.arguments[1:]))
            os.chdir(real_path)

        elif self.programme == 'pwd':
            # Print the current working directory.
            print(os.getcwd())

        elif self.programme in ('h', 'history'):
            # Access this shell's history
            history = History()

            if len(self.arguments) > 1:
                # Run a previously run command.
                history.run(int(self.arguments[1]))

            else:
                # Print the history to the user.
                print(history)

        # Return whether or not the command needs to be added to history.
        return self.programme not in ('h', 'history')

class CommandPipeList:
    """

    """
    def __init__(self, commands):
        self.commands = commands

    def run(self):
        pass

class History:
    """
    History implements the `Borg <http://code.activestate.com/recipes/66531>`
    design pattern. The idea is that the history is kept in a constant state
    no matter where it's accessed without passing around an instance reference.
    """

    # Initalises the initial state of the history object.
    __shared_state = {'commands': []}

    def __init__(self):
        self.__dict__ = self.__shared_state

    def __str__(self):
        """
        Generates a string on the history in an overly complicated manner.
        Awesome one liner though. Essentially enumerates the command list,
        formats the indexes and commands into a list of strings then joins
        them with the new line character. This was to solve a new line being
        printed at the end when using a standard for loop.
        """
        return '\n'.join('[%i]\t%s' % (index + 1, command)
                         for index, command in enumerate(self.commands))

    def run(self, command_number):
        """
        Run a previously executed command.
        """
        command = self.commands[command_number - 1]
        command.run()
        self.append(command)

    def append(self, command):
        self.commands.append(command)


def main():
    shell = Pysh()
    shell.start()

if __name__ == '__main__':
    main()
