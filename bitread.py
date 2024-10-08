#!/usr/bin/env python3
#
# Copyright (C) 2022 Brigham Young University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

'''
    bitread.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2021-2022

    A script that mimics the bitread tool from Project X-Ray. Creates a
    .bits file that addresses the location of every high bit in a design's
    bitstream.

    Arguments:
        - The bitstream file of the design for the part

    Returns:
        - List of all design bits in the format "bit_[base_frame]_[word_offset]_[bit_offset]"
'''

from lib.tile import get_xray_dir

#################################################
#                Helper functions               # 
#################################################

def parse_word(bitfile):
    '''
        Reads in one 32-bit word from the bitstream
            Arguments: The opened bitstream file
            Returns: List containing each bit starting at the LSB
    '''

    # Parse in 4 bytes (one 32-bit word) in integer form
    word_ints = []
    for i in range(4):
        byte = bitfile.read(1)
        word_ints.append(ord(byte))

    # Generate list of 32 bits in the word (LSB = index 0). The list is reversed
    # because the least significant byte comes last in the word
    word_bits = []
    for byte in reversed(word_ints):
        for i in range(8):
            word_bits.append((byte >> i) & 1)

    return word_bits


def bits_to_int(binary:list):
    '''
        Converts the binary representation of a number to its decimal form
            Arguments: List of each bit in the number
            Returns: Integer of the binary's decimal value
    '''

    int_value = 0
    for i, bit in enumerate(binary):
        int_value = int_value + bit*(2**i)
    return int_value


def read_bytes_ascii(bitfile):
    '''
        Looks at the next two bytes in the bitstream to determine the length of the field
        and reads the specified number of bytes into a string format
            Arguments: Opened bitstream, flag to determine if the bytes should be kept or not
            Returns: String of the field's ascii representation of the bytes
    '''

    # Read two bytes from the bitstream, which specify the number of bytes in the next field
    two_bytes = [ord(bitfile.read(1)), ord(bitfile.read(1))]

    # Convert bytes to binary
    read_len_bits = []
    for curr_byte in reversed(two_bytes):
        for i in range(8):
            read_len_bits.append((curr_byte >> i) & 1)

    # Convert binary to decimal and read number of bytes specified      
    read_len = bits_to_int(read_len_bits)

    # Parse part name from the number of bytes specified
    field_str = '' 
    for _ in range(read_len):
        curr_byte = ord(bitfile.read(1))
        field_str += chr(curr_byte)
    
    return field_str

##################################################
#      Organize main function into sections      #
##################################################

def find_config_packet(bitfile):
    '''
        Parses the beginning of the bitstream to find the part name and the beginning of the
        Type 2 configuration packet, which is where the configuration frames begin.
            Arguments: The opened bitstream to read
            Returns: String of the part name
    ''' 

    # First field in the header provides no useful information, skip it
    read_bytes_ascii(bitfile)

    # Second field should be the letter 'a'
    a_char = read_bytes_ascii(bitfile)
    if a_char != 'a':
        raise Exception('Unrecognized bitstream format') 

    # Next field should be the design name along with other information, we do not need it
    read_bytes_ascii(bitfile)
    bitfile.read(1)

    # Next field is the part name, get it
    part_name = read_bytes_ascii(bitfile)[:-1]
    # Series-7 names from the bitstream are incomplete
    if part_name[0] == '7':
        part_name = "xc" + part_name + "-1"

    # Decimal form of the sync word 0xAA995566
    SYNC_WORD = 2862175590
    sync_word_found = False

    # Read bytes until the sync word is found
    while not sync_word_found:
        byte = bitfile.read(1)
        # Check if current byte is equal to first byte of sync word (0xAA = 170)    
        if ord(byte) == 170:
            # Move back one byte in the file and check if the whole word is equal to the sync word
            bitfile.seek(-1, 1)
            if bits_to_int(parse_word(bitfile)) == SYNC_WORD:
                sync_word_found = True

    in_config_data    = False
    type_2_fdri_write = False
    packet_2_length   = None
    
    # Search for the start of the type 2 packet, which is where the configuration frames are
    while not in_config_data:
        word = parse_word(bitfile)
        # If type 2 packet header found, leave loop
        if word[-3:] == [0, 1, 0] and type_2_fdri_write:
            packet_2_length = sum([b<<i for i, b in enumerate(word[:27])])
            in_config_data = True
        # Some other bitstream content
        else:
            # FDRI write not yet found
            type_2_fdri_write = False
            
            # If type 1 packet header found, parse packet
            if word[-3:] == [1, 0, 0]:
                packet_1_length = sum([b<<i for i, b in enumerate(word[:11])])
                packet_1_addr   = sum([b<<i for i, b in enumerate(word[13:27])])
                packet_1_opcode = sum([b<<i for i, b in enumerate(word[27:29])])
                packet_1_data   = []
                for i in range(packet_1_length):
                    packet_1_data.append(parse_word(bitfile))
                    
                # the typical FDRI write is a type-1 packet containing FDRI and length 0
                # followed by a type-2 packet containing the configuration frames
                type_2_fdri_write = packet_1_opcode == 2 and packet_1_addr == 2 and packet_1_length == 0

    # We have read the bitstream up until the main configuration packet, exit the function
    return part_name, packet_2_length
    

def get_frame_list(part:str):
    '''
        Parses the part.json file to generate a frame list for the 7-series part
            Arguments: String of the part's name
            Returns: List containing each frame address in both binary and hexadecimal formats
    '''

    # The binary form of a Series-7 frame address is as follows:
    #   [31:26] -- Reserved
    #   [25:23] -- Block Type (Bus)
    #      [22] -- Top/Bottom Bit
    #   [21:17] -- Row Address
    #    [16:7] -- Column Address
    #     [6:0] -- Minor Address

    HALF_SCOPE = 2
    ROW_SCOPE = 4
    BUS_SCOPE = 6
    COL_SCOPE = 8
    FRAME_COUNT_SCOPE = 9

    frames = []
    curr_addr = [0] * 32
    curr_scope = 0

    # Determine the family of the series 7 part
    if 'xc7a' in part:
        family = "artix7"
    if 'xc7k' in part:
        family = "kintex7"
    if 'xc7s' in part:
        family = "spartan7"
    if 'xc7z' in part:
        family = "zynq7"

    # Open the part.json file for the part
    with open(f"{get_xray_dir()}/{family}/{part}/part.json", "r") as p_j:
        
        for line in p_j:           
            # Set corresponding bit for whether the frame's row is in the top or bottom half
            if curr_scope == HALF_SCOPE:
                if "top" in line:
                    curr_addr[22] = 0
                if "bottom" in line:
                    curr_addr[22] = 1

            # Set bits corresponding to the row number
            if curr_scope == ROW_SCOPE:
                row_num = line.split('"')[1::2]
                if row_num:
                    for i, index in enumerate(range(17, 22)):
                        curr_addr[index] = (int(row_num[0]) >> i) & 1

            # Set bits corresponding to the bus / block type
            if curr_scope == BUS_SCOPE:
                if "CLB_IO_CLK" in line:                    
                    curr_addr[23:26] = reversed([0, 0, 0])
                if "BLOCK_RAM" in line:
                    curr_addr[23:26] = reversed([0, 0, 1])
                if "CFG_CLB" in line:
                    curr_addr[23:26] = reversed([0, 1, 0])

            # Set bits corresponding to the column number
            if curr_scope == COL_SCOPE:
                col_num = line.split('"')[1::2]
                if col_num:
                    for i, index in enumerate(range(7, 17)):
                        curr_addr[index] = (int(col_num[0]) >> i) & 1

            # Create the number of frames specified with the current position data (row, column, etc.)
            # and add those frames to the list
            if curr_scope == FRAME_COUNT_SCOPE:
                if "}" not in line:
                    num_frames = int(line.strip().split(" ")[1])
                    for minor_addr in range(num_frames):
                        for index in range(7):
                            curr_addr[index] = (minor_addr >> index) & 1
                        
                        # Adding the hexadecimal and binary forms of the address to a list and adding
                        # that list to the frames list
                        frame_addr_hex = hex(bits_to_int(curr_addr)).lstrip("0x").rjust(8, "0")
                        frames.append([frame_addr_hex, curr_addr.copy()])


            # Increment curr_scope counter when scope changes
            if "{" in line:
                curr_scope += 1
            # Decrement curr_scope counter when scope changes
            if "}" in line:
                curr_scope -= 1


    return sorted(frames)


def parse_config_packet(bitfile, config_packet_length:int, frames:list):
    '''
        Parses the main configuration packet for all high bits
            Arguments: The opened bitstream file and the list of frame addresses
            Returns: List of all high bits in the configuration packet
    '''

    # The number of words in a frame
    FRAME_LENGTH = 101
    
    
    # check if config packet is multiple of frame length
    if config_packet_length % FRAME_LENGTH != 0:
        print("ERROR: Config packet length must be multiple of frame length")
        exit()
        
    # frames remaining to be parsed
    frames_remaining = config_packet_length
    
    # List of high bits
    bits = []
    # Keep track of the previous frame so a row change can be detected
    prev_frame = frames[0].copy()

    # Iterate through each frame in the frame list
    for frame in frames:

        # Skip 2 frames worth of bits whenever the row changes
        if prev_frame[1][17:23] != frame[1][17:23]:
            frames_remaining -= FRAME_LENGTH*2
            for i in range(FRAME_LENGTH*2):
                parse_word(bitfile)

        # Iterate for the number of words specified for this architecture's frame
        for word_offset in range(FRAME_LENGTH):

            frames_remaining -= 1
            word = parse_word(bitfile)
            
            # Iterate through each bit in the word
            for bit_offset, bit in enumerate(word):
                # The first 13 bits of the 51st word per frame are reserved for the "horizontal clock row" in series-7
                in_clock_row_bits = (word_offset == 50 and bit_offset <= 12)
                # Add every high bit to the bits list
                if bit == 1 and not in_clock_row_bits:
                    word_offset_str = str(word_offset).rjust(3, "0")
                    bit_offset_str = str(bit_offset).rjust(2, "0")
                    bits.append(f'bit_{frame[0]}_{word_offset_str}_{bit_offset_str}')
                    
        prev_frame = frame.copy()

    # now, only two dummy frames should remain to be read from the config packet
    if frames_remaining != 2*FRAME_LENGTH:
        print("ERROR: Config packet not fully parsed.")
        exit()

    return bits

##################################################
#                 Main Function                  #
##################################################

def get_high_bits(bitstream:str):
    '''
        Generates a list of all the high bits in a bitstream's main configuration packet
            Arguments: The bitstream's file path
            Returns: List of all design bits
    '''

    # Begin reading the bitstream
    with open(bitstream, "rb") as bitfile:
        
        # Read through header and beginning parts of bitfile, get part name and config packet length along the way
        part, config_packet_length = find_config_packet(bitfile)

        # Get a list of all the frames for the part. Each frame is a list with the hexadecimal
        # and binary forms of the frame address for convenience.
        if "xc7" in part:
            frames = get_frame_list(part)
        else:
            print("ERROR: Only Series-7 parts are supported by BFAT")
            exit()

        # Parses the configuration packet and determines the addresses of high bits in the bitstream
        bits = parse_config_packet(bitfile, config_packet_length, frames)

    return bits

def main(args):
    '''
        Main function: Creates a readable list of the high bits in the provided bistream
        and writes it to a corresponding .bits file.
    '''

    # Run bitread to generate a list of the design bits
    bits = get_high_bits(args.bitstream)

    # Output the list to a .bits file if running the script by itself
    with open(f'{args.bitstream}s', "w") as bits_file:
        for bit in bits:
            bits_file.write(bit + "\n")

if __name__ == "__main__":
    import argparse

    # Create argument parser for running bitread by itself
    parser = argparse.ArgumentParser(description="Remake of prjxray bitread tool in python for BFAT project")
    parser.add_argument('bitstream', help='bitstream file to be converted to a .bits file')
    args = parser.parse_args()

    main(args)
