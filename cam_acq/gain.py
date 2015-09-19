from collections import defaultdict
import subprocess
import numpy as np
from command import Command


class Gain(object):

    """Gain class

    Attributes:
        gain_dict: A defaultdict of lists where the keys are the wells and
        each list (value) contains the gain values of the (four) channels.
    """

    def __init__(self, gain_dict, imaging_dir, init_gain, r_script, job_list,
                 pattern_g, pattern, first_job, last_well, end_10x=None,
                 end_40x=None, end_63x=None, template_file=None, coords=None):
        self.gain_dict = gain_dict
        self.imaging_dir = imaging_dir
        self.init_gain = init_gain
        self.r_script = r_script
        self.job_list = job_list
        self.pattern_g = pattern_g
        self.pattern = pattern
        self.first_job = first_job
        self.last_well = last_well
        self.end_10x = end_10x
        self.end_40x = end_40x
        self.end_63x = end_63x
        self.template_file = template_file
        if self.template_file:
            csv = File(self.template_file)
            self.template = csv.read_csv('gain_from_well', ['well'])
            self.last_well = sorted(self.template.keys())[-1]
        self.coords = coords
        self.green_sorted = defaultdict(list)
        self.medians = defaultdict(int)

    def process_output(self, well, output, dict_list):
        """Function to process output from the R scripts."""
        for c in output.split():
            dict_list[well].append(c)
        return dict_list

    def calc_gain(self, filebases, fin_wells):
        """Function to run R scripts and calculate gain values for
        the wells."""
        # Get a unique set of filebases from the csv paths.
        filebases = sorted(set(filebases))
        # Get a unique set of names of the experiment wells.
        fin_wells = sorted(set(fin_wells))
        for fbase, well in zip(filebases, fin_wells):
            print(well)
            try:
                print('Starting R...')
                r_output = subprocess.check_output(['Rscript',
                                                    self.r_script,
                                                    self.imaging_dir,
                                                    fbase,
                                                    self.init_gain
                                                    ])
                self.gain_dict = self.process_output(well, r_output,
                                                     self.gain_dict)
            except OSError as e:
                print('Execution failed:', e)
                sys.exit()
            except subprocess.CalledProcessError as e:
                print('Subprocess returned a non-zero exit status:', e)
                sys.exit()
            print(r_output)
        return self.gain_dict

    def distribute_gain(self):
        """Function to collate gain values and distribute them to the wells as
           to efficiently be able to scan all the wells."""
        self.green_sorted = defaultdict(list)
        self.medians = defaultdict(int)
        for i, c in enumerate(['green', 'blue', 'yellow', 'red']):
            mlist = []
            for k, v in self.gain_dict.iteritems():
                # Sort gain data into a list dict with green gain as key
                # and where the value is a list of well ids.
                if c == 'green':
                    # Round gain values to multiples of 10 in green channel
                    if self.end_63x:
                        green_val = int(min(round(int(v[i]), -1), 800))
                    else:
                        green_val = int(round(int(v[i]), -1))
                    if self.template:
                        for well in self.template[k]:
                            self.green_sorted[green_val].append(well)
                    else:
                        self.green_sorted[green_val].append(k)
                else:
                    # Find the median value of all gains in
                    # blue, yellow and red channels.
                    mlist.append(int(v[i]))
                    self.medians[c] = int(np.median(mlist))
        return

    def set_gain(self, com, channels, job_list):
        for i, c in enumerate(channels):
            gain = str(c)
            if i < 2:
                detector = '1'
                job = job_list[i]
            if i >= 2:
                detector = '2'
                job = job_list[i - 1]
            com.gain_com(exp=job, num=detector, value=gain) + '\n'
        return com

    # #FIXME:50 Merge get_com and get_init_com functions, trello:egmsbuN8
    def get_com(self):
        dx = 0
        dy = 0
        # Lists for storing command strings.
        com_list = []
        end_com_list = []
        for gain, wells in self.green_sorted.iteritems():
            com = Command()
            end_com = []
            channels = [gain,
                        self.medians['blue'],
                        self.medians['yellow'],
                        self.medians['red']
                        ]
            com = self.set_gain(com, channels, self.job_list)
            if self.coords is None:
                self.coords = {}
            for well in sorted(wells):
                for i in range(2):
                    for j in range(2):
                        # Only add selected fovs from file (arg) to cam list
                        fov = '{}--X0{}--Y0{}'.format(well, j, i)
                        if fov in self.coords.keys():
                            dx = self.coords[fov][0]
                            dy = self.coords[fov][1]
                            fov_is = True
                        elif not self.coords:
                            fov_is = True
                        else:
                            fov_is = False
                        if fov_is:
                            com.cam_com(self.pattern,
                                        well,
                                        'X0{}--Y0{}'.format(j, i),
                                        dx,
                                        dy
                                        )
                            end_com = ['CAM',
                                       well,
                                       'E0' + str(self.first_job + 2),
                                       'X0{}--Y0{}'.format(j, i)
                                       ]
            # Store the commands in lists.
            com_list.append(com.com)
            end_com_list.append(end_com)
        return {'com': com_list, 'end_com': end_com_list}

    def get_init_com():
        wells = []
        if self.template:
            # Selected wells from template file.
            wells = self.template.keys()
        else:
            # All wells.
            for u in range(int(Command().get_wfx(self.last_well))):
                for v in range(int(Command().get_wfy(self.last_well))):
                    wells.append('U0' + str(u) + '--V0' + str(v))
        # Lists and strings for storing command strings.
        com_list = []
        end_com_list = []
        com = Command()
        end_com = []
        # Selected objective gain job cam command in wells.
        for well in sorted(wells):
            for i in range(2):
                com.cam_com(self.pattern_g, well, 'X0{}--Y0{}'.format(i, i),
                            '0', '0')
                end_com = ['CAM', well, 'E0' + str(2),
                           'X0{}--Y0{}'.format(i, i)]
            com_list.append(com.com)
            end_com_list.append(end_com)
            com = Command()
        # Concatenate commands to one string if dry objective
        if self.end_10x or self.end_40x:
            com.com = ''.join(com_list)
            com_list = []
            com_list.append(com.com)
            end_com_list = []
            end_com_list.append(end_com)
        return {'com': com_list, 'end_com': end_com_list}
