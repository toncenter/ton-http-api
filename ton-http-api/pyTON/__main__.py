import multiprocessing as mp
from pyTON.cli import main


if __name__ == '__main__':
    mp.set_start_method('fork')
    main()
