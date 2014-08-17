#! /usr/bin/env python3

import os
import sys
import fcntl
import shlex
import signal
import struct
import termios
import readline
import itertools
import threading
import subprocess

__author__ = 'Chris Morgan'


# Use this later for flexibility.
def get_prompt():

    user = os.environ['USER']
    dir = os.getcwd().split('/')[-1]

    return '%s : %s > ' % (user, dir)


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

    def start(self):
        """
        Starts the shell, listening until 'exit' is called.
        """

        signal.signal(signal.SIGINT, (lambda sig, frame: Pysh.interupt_prompt(get_prompt())))
        signal.signal(signal.SIGTSTP, Command.stop_process)

        while True:

            # Stop pycharm complaining.
            input_string = None

            try:
                input_string = input(get_prompt())
            except EOFError:
                exit()

            if not sys.stdin.isatty():
                print(input_string)

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
            elif commands:
                result = commands[0].run()
                if result.__class__.__name__ == 'tuple':
                    pid, status = result
                    if status is None:
                        self.jobs.add_job(commands[0], pid)

                if result:
                    self.history.append(commands[0])

    @staticmethod
    def interupt_prompt(string=''):
        # Grab the number of rows and columns of the terminal so we can clear it.
        (rows, columns) = struct.unpack('hh', fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, '    '))

        # Get the length of the current text in the terminal.
        line_length = len(readline.get_line_buffer()) + len(get_prompt())

        # This clears the line and moves the cursor down.
        sys.stdout.write('\x1b[2K')
        sys.stdout.write('\x1b[1A\x1b[2K' * int(line_length / columns))
        sys.stdout.write('\x1b[0G')

        print(string)

        sys.stdout.write(get_prompt() + readline.get_line_buffer())
        sys.stdout.flush()

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

    __current_pid = 0

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

        if self.background:
            # Return the child pid immediatly when running in the background.
            return child, None
        else:
            # If the process is not going to run in the background, wait for
            # the programme to finish.
            Command.__current_pid = child
            try:
                child, status = os.wait()
            except InterruptedError:
                status = None

            Command.__current_pid = 0
            return child, status

    @staticmethod
    def stop_process(sig, frame):
        if Command.__current_pid:
            os.kill(Command.__current_pid, signal.SIGSTOP)

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
            if len(self.arguments) == 1:
                os.chdir(os.path.expanduser('~'))
            else:
                real_path = os.path.expanduser(''.join(self.arguments[1:]))
                try:
                    os.chdir(real_path)
                except FileNotFoundError as e:
                    print('no such file or directory: %s' % ' '.join(self.arguments[1:]))

        elif self.programme == 'pwd':
            # Print the current working directory.
            print(os.getcwd())

        elif self.programme == 'jobs':
            print(Jobs())

        elif self.programme in ('h', 'history'):
            # Access this shell's history
            history = History()

            if len(self.arguments) > 1:
                # Run a previously run command.
                return history.run(int(self.arguments[1]))

            else:
                # Print the history to the user.
                print(history)
                return True

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

        if command_number > len(self.commands):
            print('no record for: %i' % command_number)
            return True
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
        return '\n'.join('[%i]\t%s' % (index + 1, str(job))
                         for index, job in enumerate(self.jobs))

    def add_job(self, command, pid):
        job = Job(command, pid, len(self.jobs) + 1)
        self.jobs.append(job)
        print('[%i]\t%s' % (len(self.jobs), str(job.command)))
        threading.Thread(target=self.wait_job, args=tuple([job])).start()

    @staticmethod
    def wait_job(job):
        os.waitpid(job.pid, 0)
        Pysh.interupt_prompt('[%i]\t%i done\t%s' % (job.job_number, job.pid, str(job.command)))


class Job:

    def __init__(self, command, pid, job_number):
        self.command = command
        self.pid = pid
        self.job_number = job_number

    def __str__(self):
        process = subprocess.Popen(['ps', '-p', str(self.pid), '-o', 'state'], stdout=subprocess.PIPE)
        status = process.stdout.readlines()[1].strip().decode('ascii')[0]  # Eww
        process.wait()
        if status in ['S', 'I']:
            status = 'sleeping'
        elif status == 'R':
            status = 'running'
        elif status == 'Z':
            status = 'zombie'
        elif status == 'T':
            status = 'stopped'
        else:
            status = 'dunno...'
        return '%s %s' % (status, str(self.command))


if __name__ == '__main__':
    Pysh().start()
