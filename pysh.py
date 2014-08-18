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

"""
Author: Chris Morgan
UPI:    cmor149
ID:     1744263
Email:  chris.j.r.morgan@gmail.com
"""


# Use this later for flexibility.
def get_prompt():

    return 'psh> '


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

    __built_in_commands = ('h', 'history', 'cd', 'pwd', 'exit', 'jobs', 'fg', 'bg', 'kill')

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

        # Set up signals to handle crtl + z and ctrl + c
        signal.signal(signal.SIGINT, (lambda sig, frame: Pysh.interupt_prompt(get_prompt())))
        signal.signal(signal.SIGTSTP, (lambda sig, frame: self.jobs.stop_process()))

        # Infinite loop, woo!
        while True:

            # Stop pycharm complaining.
            input_string = None

            try:
                input_string = input(get_prompt())
            except EOFError:  # If we hit the end of a file or user types ctrl + d.
                self.jobs.kill_all()
                exit()

            # For the markers.
            if not sys.stdin.isatty():
                print(input_string)

            # Get shell words from input
            command_strings = self.parse_line(input_string)

            if not command_strings:
                continue

            if command_strings[-1][-1] == '&':
                background = True
                command_strings[-1].pop()
            else:
                background = False

            if len(command_strings) < 2:
                if command_strings[0][0] in self.__built_in_commands:
                    command = BuiltInCommand(command_strings[0], background=background)
                else:
                    command = Command(command_strings[0], background=background)
            else:
                commands = []
                for sub_command in command_strings:
                    if sub_command[0] in self.__built_in_commands:
                        commands.append(BuiltInCommand(sub_command))
                    else:
                        commands.append(Command(sub_command))
                command = CommandPipeList(commands, background=background)

            result = self.jobs.run(command)
            if result.__class__.__name__ == 'tuple':
                pid, status = result
                if status is None:
                    self.jobs.add_job(command, pid)

            if result:
                self.history.append(command)

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

    def run(self, read_fd=sys.stdin.fileno(), write_fd=sys.stdout.fileno(), temp_bg=False):
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
            try:
                os.execvp(self.programme, self.arguments)
            except FileNotFoundError as e:
                print('command not found: %s' % self.programme)
                return

        if self.background or temp_bg:
            # Return the child pid immediately when running in the background.
            return child, None
        else:
            # If the process is not going to run in the background, wait for
            # the programme to finish.
            Jobs().set_current_pid(child)
            try:
                child, status = os.wait()
            except InterruptedError:
                status = 'stopped'
            return child, status


    def __str__(self):
        if self.background:
            ampersand = '&'
        else:
            ampersand = ''

        return ' '.join(self.arguments + [ampersand])


class BuiltInCommand(Command):

    def run(self, read_fd=sys.stdin.fileno(), write_fd=sys.stdout.fileno(), temp_bg=False):
        """
        Run the built in command.
        """
        if self.programme == 'exit':
            # Break out of loop.
            Jobs().kill_all()
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
            # List jobs running
            jobs = Jobs()
            if jobs.no_jobs():
                print(jobs)

        elif self.programme == 'fg':
            # Continue a stopped process in the foreground. This does not work for processing that are currently
            # running.
            if len(self.arguments) > 1:
                try:
                    Jobs().start_process(job_number=int(self.arguments[1]))
                except NoSuchJob as e:
                    print(e)
            else:
                Jobs().start_process()

        elif self.programme == 'bg':
            # Continue a stopped process in the background.
            if len(self.arguments) > 1:
                try:
                    Jobs().start_process(job_number=int(self.arguments[1]), background=True)
                except NoSuchJob as e:
                    print(e)
            else:
                Jobs().start_process(background=True)

        elif self.programme == 'kill':
            if len(self.arguments) == 1:
                print('kill takes exactly 1 argument')
            else:
                try:
                    Jobs().kill(int(self.arguments[1]))
                except NoSuchJob as e:
                    print(e)

        elif self.programme in ('h', 'history'):
            # Access this shell's history
            history = History()

            if len(self.arguments) > 1:
                # Run a previously run command.
                return history.run(int(self.arguments[1]))

            elif history.no_history():
                # Print the history to the user.
                print(history)
                return True

        # Return whether or not the command needs to be added to history.
        return self.programme not in ('h', 'history')


class CommandPipeList:
    """
    manages a piping for the shell
    """
    def __init__(self, commands, background=False):
        self.commands = commands
        self.background = background

    def run(self):
        """
        runs the list of commands, chaining pipes between them to allow throughput of data.
        """

        child = os.fork()

        if child == 0:

            # We need to keep a reference to the last read pipe file descriptor, set it as stdin for convenience.
            last_read = sys.stdin.fileno()

            # Cycle through all of the commands (bar the last)
            for command in self.commands[:-1]:

                # Create the read and write pipes for the command to use and then run the command.
                # Temporarily run it in the background to prevent locking.
                read, write = os.pipe()
                command.run(read_fd=last_read, write_fd=write, temp_bg=True)

                # So we can use the new pipe in the next iteration.
                last_read = read

            # Run the last command in the list, print to stdout.
            self.commands[-1].run(read_fd=last_read, write_fd=sys.stdout.fileno())

            # Finished piping off the commands, exit.
            exit()

        if not self.background:
            # Wait for the pipe running process to finish.
            Jobs().set_current_pid(child)
            try:
                child, status = os.wait()
            except InterruptedError:
                status = 'stopped'
            return child, status

        return child, None

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
        if not self.__dict__:
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

    def no_history(self):
        return len(self.commands)


class Jobs:
    """
    Jobs are a bit of a mess, the functionality is a bit all over the place and needs to be consolidated, but I've run
    out of time.

    Jobs handles background processes, as well as running commands (this really should be move out).
    Jobs is also another example of the Borg design pattern.
    """

    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        if not self.__dict__:
            self.jobs = []
            self.stopped_stack = []
            self.current_pid = 0

    def __str__(self):
        """
        creates a string that lists all the background jobs
        :return: a string of all the jobs
        """
        out = ''
        for job in self.jobs:
            out += '[%i]\t%s\n' % (job.job_number, str(job))
        return out[:-2]

    def add_job(self, command, pid):

        new_job_number = 1
        if self.jobs:
            new_job_number = self.jobs[-1].job_number + 1

        job = Job(command, pid, new_job_number)
        self.jobs.append(job)
        print('[%i]\t%s' % (new_job_number, str(job.command)))

        # This does something different to bash, we start a new thread to wait for the process to finish and then
        # notify us when it has. More like zsh.
        threading.Thread(target=self.wait_job, args=tuple([job])).start()

    def start_process(self, job_number=0,background=False):

        if not self.stopped_stack:
            print('no stopped processes')
            return

        if job_number:
            job = self.stopped_stack.pop(self.stopped_stack.index(self.get_job_by_number(job_number)))
        else:
            job = self.stopped_stack.pop()

        self.current_pid = 0
        os.kill(job.pid, signal.SIGCONT)
        if not background:
            self.jobs.pop(self.jobs.index(job))
            try:
                child, status = os.waitpid(job.pid, 0)
            except InterruptedError:
                self.stopped_stack.append(job)
                self.jobs.append(job)
        else:
            # This does something different to bash, we start a new thread to wait for the process to finish and then
            # notify us when it has. More like zsh.
            threading.Thread(target=self.wait_job, args=tuple([job])).start()

    def wait_job(self, job):
        # Wait for the process to finish and notify user.
        os.waitpid(job.pid, 0)
        Pysh.interupt_prompt('[%i]\t%i %s\t%s' % (job.job_number, job.pid, job.get_status(), str(job.command)))
        self.jobs.pop(self.jobs.index(job))

    def run(self, command):
        result = command.run()
        if result.__class__.__name__ == 'tuple' and result[1] == 'stopped':
            new_job_number = 1
            if self.jobs:
                new_job_number = self.jobs[-1].job_number + 1

            new_job = Job(command, self.current_pid, new_job_number)
            self.stopped_stack.append(new_job)
            self.jobs.append(new_job)
            print('[%i]\t%s' % (new_job_number, str(command)))
        self.current_pid = 0
        return result

    def get_job_by_number(self, job_number):
        for job in self.jobs:
            if job.job_number == job_number:
                return job
        raise NoSuchJob(job_number)

    def no_jobs(self):
        return len(self.jobs)

    def stop_process(self, job_number=0):

        if job_number:
            job = self.get_job_by_number(job_number)
            if job:
                pid = job.pid
            else:
                pid = 0
        else:
            pid = self.current_pid
        if pid:
            os.kill(pid, signal.SIGSTOP)

    def set_current_pid(self, pid):
        self.current_pid = pid

    def kill(self, job_number):
        job = self.get_job_by_number(job_number)
        if job:
            os.kill(job.pid, signal.SIGKILL)

    def kill_all(self):
        """
        Kills all background processes.
        """
        for job in self.jobs:
            os.kill(job.pid, signal.SIGKILL)


class Job:

    def __init__(self, command, pid, job_number):
        self.command = command
        self.pid = pid
        self.job_number = job_number

    def get_status(self):
        """
        Get the status of the job, uses subprocess for convenience.
        """
        process = subprocess.Popen(['ps', '-p', str(self.pid), '-o', 'state'], stdout=subprocess.PIPE)

        out = process.stdout.readlines()

        if len(out) == 1:
            return 'done'

        status = out[1].strip().decode('ascii')[0]  # Eww
        process.wait()
        if status == 'S':
            return 'sleeping'
        elif status == 'I':
            return 'idle'
        elif status == 'R':
            return 'runnable'
        elif status == 'Z':
            return 'zombie'
        elif status == 'T':
            return 'stopped'
        else:
            return 'bigfoot'  # This should never happen.

    def __str__(self):
        status = self.get_status()
        if status == 'zombie':
            os.waitpid(self.pid, 0)
            status = 'done'
        return '%s %s' % (status, str(self.command))


class NoSuchJob(Exception):
    def __init__(self, job_number):
        self.job_number = job_number

    def __str__(self):
        return 'no such job: %s' % self.job_number


if __name__ == '__main__':
    Pysh().start()
