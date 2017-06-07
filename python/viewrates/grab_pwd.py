#!/usr/bin/python
'''
Script to grab the password from a MySQL configuration file and store it
in a file format readable by the `sqoop` command line utility.

Copyright (c) 2017 Morten Wang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

def grab_password(input_file, output_file):
    with open(output_file, 'w') as outfile:
        with open(input_file, 'r') as infile:
            for line in infile:
                try:
                    (key, value) = line.strip().split('=')
                    key = key.strip()
                    value = value.strip()
                    if key == 'password':
                        outfile.write(value)
                except ValueError:
                    # not a key/value line
                    continue
            
def main():
    import argparse

    cli_parser = argparse.ArgumentParser(
        description="script to grab the password from a MySQL configuration file and store it in a file that sqoop can read"
    )

    # Verbosity option
    cli_parser.add_argument('-v', '--verbose', action='store_true',
                            help='write informational output')

    cli_parser.add_argument("input_file",
                            help="path to the MySQL configuration file")

    cli_parser.add_argument("output_file",
                            help="path to the output file")
    
    args = cli_parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    grab_password(args.input_file, args.output_file)
    return()

if __name__ == '__main__':
    main()
