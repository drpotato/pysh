#! /usr/bin/env python3

import os
from subprocess import call


class Command:

    def __init__(self, command, args):
        self.command = command
        self.args = args

    def run(self):
        output, code = call([command] + args)
        print(output)
        return output, code


def main():

    while True:

        # Grab user input and split it up into command and args.
        command_array = input('=> ').split()
        command, args = command_array[0], command_array[1:]

        # Switch statement to determine command behaviour.
        if command == 'exit':
            break
        elif command == 'cd':
            os.chdir(' '.join(args))
        else:
            print(call([command] + args))


if __name__ == '__main__':
    main()
