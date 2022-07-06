# BFAT (Bitstream Fault Analysis Tool)

---

## About:

BFAT is a tool used for analysis of of a design's bitstream to evaluate and report any relevant information about given fault bits as well as any errors that they would cause in the design's implementation. BFAT is being used for research purposes and is currently under development. So far BFAT supports most Xilinx 7-Series FPGAs that are documented in the [Project X-Ray database](https://github.com/f4pga/prjxray-db). The full list of parts can be found below in the "Supported Parts" section. The tool is run in python and consists of the following scripts:

- `bfat.py`: The main script that is run on a design and creates a .txt file to report the information found.
- `bitread.py` : python tool used to convert bitstream to ascii representation of high bits in bitstream and identify the part used to implement the provided design. Can also be run by itself to convert a bitstream to a .bits file containing the ascii representation of the high bits in the bitstream.

Scripts included from the local library:

- `tile.py`: supplementary script containing the created dataclasses to store the information on the tiles and routing muxes for the given FPGA design.
- `bit_definitions.py`: supplementary script that uses created dataclasses and program arguments to define and evaluate each of the given fault bits.
- `file_processing.py`: supplementary script that deals with all external file reading and parsing.
- `statistics_footer.py`: supplementary script that reads the report data for the design and adds on a footer at the end of the report file to report some statistics of the design and faults found.
- `rtmux_modeling.py`: supplementary script that models and prints the models of routing muxes on a low level of abstraction for better understanding of FPGA routing systems (currently unused in main script).
- `setup.sh`: bash script used to create the python virtual environments and install the necessary packages for running BFAT.

BFAT requires the use of a version of Vivado to read dcp files in order to retrieve information about the design being analyzed.

BFAT utilizes the ProjectXray database in its design analysis and clones the database repo from Github during setup.

---

## BFAT Process Flowchart
![Image](./bfat_flowchart.png)

---

## Installation and Setup

Clone the BFAT repo from Github along with its submodule

```
    git clone --recurse-submodules https://github.com/byuccl/bfat.git
    cd bfat
```

To get the data from the provided checkpoint file, BFAT will open a pipe to Vivado and retrieve information through tcl commands. Make sure that you have Vivado installed on your system
* We recommend version 2021.2 or later, as earlier versions are untested and we cannot guarantee that they will work

BFAT requires python 3.9 or later. Install a supported version if you do not already have one in your system.

---

## How to Use BFAT

1. If you have not sourced a version of Vivado, do so:
```
    source /opt/Xilinx/Vivado/<vivado_version>/settings64.sh
```

2. Run the bfat.py script providing it with:
    - The bitstream of the design to be analyzed
    - A dcp checkpoint file of the routed design to be analyzed
    - A list of fault bits to evaluate in a .json file (see `docs/fault_bit_lists.md` for details on formatting)

3. (Optional) Using the `-of` flag you can specify the file the fault report will be output to. If not used, the report will be saved to a file with a generated name in the current directory.

To see more specifics on running BFAT, look at the help information provided by running `python3 bfat.py -h`

---

## Supported Parts:

### Artix-7
- xc7a50t family
- xc7a100t family
- xc7a200t family

### Kintex-7
- xc7k70t family

### Spartan-7
- xc7s50 family

### Zynq-7000
- xc7z010 family
- xc7z020 family
