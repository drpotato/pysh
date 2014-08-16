#! /usr/bin/env python3

import os
import sys
import shlex
import signal
import itertools

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

    __built_in_commands = ('h', 'history', 'cd', 'pwd', 'exit', 'jobs')

    def __init__(self):
        """
        Initialises the Pysh instance.
        """
        self.history = History()
        self.jobs = Jobs()
        self.prompt = '> '  # TODO: Add customisation.

    def start(self):
        """
        Starts the shell, listening until 'exit' is called.
        """

        signal.signal(signal.SIGINT, self.do_nothing)
        signal.signal(signal.SIGTSTP, self.do_nothing)

        while True:

            # Stop pycharm complaining.
            input_string = None

            try:
                input_string = input(self.prompt)
            except EOFError:
                exit()

            # Get shell words from input
            command_strings = self.parse_line(input_string)

            if command_strings and command_strings[-1][-1] == '&':
                background = True
                command_strings[-1].pop()
            else:
                background = False


            # Build the list of commands to run. Built in commands are differentiated from other commands.
            commands = []
            for command in command_strings:
                if command[0] in self.__built_in_commands:
                    commands.append(BuiltInCommand(command, background=background))
                else:
                    commands.append(Command(command, background=background))

            # If there are multiple commands, we need to create a piping list, otherwise just run the command.
            if len(commands) > 1:
                command = CommandPipeList(commands, background=background)
                command.run()
                self.history.append(command)
            elif commands and commands[0].run():
                self.history.append(commands[0])


    @staticmethod
    def do_nothing(signal, frame):
        pass


    @staticmethod
    def parse_line(line):
        """
        Breaks the line up into shell words.
        :returns: Returns a list of
        :rtype:
        """
        shell_segments = shlex.shlex(line, posix=True)
        shell_segments.whitespace_split = False
        shell_segments.wordchars += '#$+-,./?@^='

        return [list(sub_list) for separator, sub_list in
                itertools.groupby(list(shell_segments), lambda word: word == '|') if not separator]


class Command:

    def __init__(self, arguments, background=False):
        """
        Initialises a Command instance.

        :param programme:   name of programme to be executed
        :type programme:    str or unicode
        :param arguments:   arguments for the programme
        :type arguments:    list([str, ...])
        :param background:  whether to run program or not
        :type background:   bool
        """
        self.programme = arguments[0]
        self.arguments = arguments
        self.background = background

    def run(self, read_fd=sys.stdin.fileno(), write_fd=sys.stdout.fileno()):
        """
        Runs the command and manages the child process.

        :returns:   returns child process id and exist status
        :rtype:     tuple(int, int)
        """
        # Fork the current process and store the child process id for later
        # use.
        child = os.fork()

        if child == 0:
            # If this process is the child, replace current execution with
            # programme to run.

            # Set up input/output.
            os.dup2(read_fd, sys.stdin.fileno())
            os.dup2(write_fd, sys.stdout.fileno())

            # Replace the current programme with execvp
            os.execvp(self.programme, self.arguments)

        # If the process runs in the background, we still need to return this.
        status = None

        if not self.background:
            # If the process is not going to run in the background, wait for
            # the programme to finish.
            _, status = os.wait()

        return child, status

    def __str__(self):
        if self.background:
            ampersand = '&'
        else:
            ampersand = ''

        return ' '.join(self.arguments + [ampersand])


class BuiltInCommand(Command):

    def run(self, read_fd=sys.stdin.fileno(), write_fd=sys.stdout.fileno()):
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
    def __init__(self, commands, background=False):
        self.commands = commands
        self.background = background

    def run(self):

        child = os.fork()

        if child == 0:

            last_read = sys.stdin.fileno()

            for command in self.commands[:-1]:

                read, write = os.pipe()
                command.background = True
                command.run(read_fd=last_read, write_fd=write)

                last_read = read

            self.commands[-1].run(read_fd=last_read, write_fd=sys.stdout.fileno())

            # Finished piping off the commands, exit.
            exit()

        # Wait for the pipe running process to finish.
        if not self.background:
            _, status = os.wait()
            return status


    def __str__(self):
        return ' | '.join([str(command) for command in self.commands])


class History:
    """
    History implements the `Borg <http://code.activestate.com/recipes/66531>`
    design pattern. The idea is that the history is kept in a constant state
    no matter where it's accessed without passing around an instance reference.
    """

    # Initialises the initial state of the history object.
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state

        # If commands doesn't exist in the dictionary, add it.
        if 'commands' not in self.__dict__:
            self.commands = []

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


class Jobs:

    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        if 'jobs' not in self.__dict__:
            self.jobs = []

    def __str__(self):
        return '\n'.join('[%i]\t%s' % (index + 1, job)
                         for index, job in enumerate(self.jobs))

    def add_job(self, command, pid):
        job = Job(command, pid)
        self.jobs.append(job)

class Job:

    def __init__(self, command, pid):
        self.command = command
        self.pid = pid


def main():
    shell = Pysh()
    shell.start()

if __name__ == '__main__':
    main()
