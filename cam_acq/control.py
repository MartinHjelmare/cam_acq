import os
import re
from collections import defaultdict
from pkg_resources import resource_string
from socket_client import Client
from command import Command
from gain import Gain


class Control(object):

    # #DONE:60 Which args should be optional in init function, Control class, trello:Tg7I1eTe
    def __init__(self, imaging_dir, host, init_gain, working_dir, last_well,
                 last_field, first_job, coord_file=None, input_gain=None,
                 template_file=None, end_10x=None, end_40x=None, end_63x=None,
                 gain_only=None):
        self.imaging_dir = imaging_dir
        self.host = host
        self.init_gain = init_gain
        self.working_dir = working_dir
        self.last_well = last_well
        self.last_field = last_field
        self.first_job = first_job
        self.coord_file = coord_file
        self.input_gain = input_gain
        self.template_file = template_file
        self.end_10x = end_10x
        self.end_40x = end_40x
        self.end_63x = end_63x
        self.gain_only = gain_only
        self.r_script = resource_string(__name__, 'data/gain.r')
        # Create socket
        self.sock = Client()
        # Port number
        self.port = 8895
        # commands
        self.del_com = Command().del_com()
        self.start_com = Command().start_com()
        self.stop_com = Command().stop_com()
        self.camstart_com = Command().camstart_com()

        # dicts of lists to store wells with gain values for
        # the four channels.
        self.gain_dict = defaultdict(list)
        self.saved_gains = defaultdict(list)

        # #RFE:0 Assign job vars by config file, trello:UiavT7yP
        # #RFE:10 Assign job vars by parsing the xml/lrp-files, trello:d7eWnJC5

        # Job and pattern variables and names
        # AF job names and settings are not used when not using the drift AF.
        #af_job_10x = 'af10xcam'
        #afr_10x = '200'
        #afs_10x = '41'
        #af_job_40x = 'af40x'
        #afr_40x = '105'
        #afs_40x = '106'
        #af_job_63x = 'af63x'
        #afr_63x = '50'
        #afs_63x = '51'
        self.pattern_g_10x = 'pattern7'
        self.pattern_g_40x = 'pattern8'
        self.pattern_g_63x = 'pattern9'
        self.job_10x = ['job22', 'job23', 'job24']
        self.pattern_10x = 'pattern10'
        self.job_40x = ['job7', 'job8', 'job9']
        self.pattern_40x = 'pattern2'
        self.job_63x = ['job10', 'job11', 'job12']
        self.pattern_63x = 'pattern3'

    def parse_reply(self, reply, root):
        """Function to parse the reply from the server to find the
        correct file path."""
        reply = reply.replace('/relpath:', '')
        paths = reply.split('\\')
        for path in paths:
            root = os.path.join(root, path)
        return root

    def search_imgs(self, line):
        error = True
        count = 0
        while error and count < 2:
            try:
                root = self.parse_reply(line, self.imaging_dir)
                img = CamImage(root)
                print(img.name)
                error = False
                return img
            except TypeError as e:
                error = True
                count += 1
                time.sleep(1)
                print('No images yet... but maybe later?', e)
        return None

    # #DONE:20 Add get_imgs function, trello:nh2R6RWR

    def get_imgs(self, path, imdir, job_order, f_job=None, img_save=None,
                 csv_save=None):
        """Function to handle the acquired images, do renaming,
        max projections etc."""
        if f_job is None:
            f_job = 2
        if img_save is None:
            img_save = True
        if csv_save is None:
            csv_save = True
        # Get all image paths in well.
        img_paths = Directory(path).get_all_files('*' + job_order + '*.tif')
        new_paths = []
        metadata_d = {}
        for img_path in img_paths:
            img = CamImage(img_path)
            img_array = img.read_image()
            # #FIXME:20 Breakout new renaming function (DRY), trello:rKNNQvha
            if img.E_id_int == f_job:
                new_name = os.path.normpath(os.path.join(
                    path, ('{}--{}--{}--{}--{}.ome.tif'.format(
                        img.well, img.E_id, img.field, img.Z_id, img.C_id))))
            elif img.E_id_int == f_job + 1 and img.C_id == 'C00':
                new_name = os.path.normpath(os.path.join(
                    path, ('{}--{}--{}--{}--C01.ome.tif'.format(
                        img.well, img.E_id, img.field, img.Z_id))))
                img.C_id = 'C01'
            elif img.E_id_int == f_job + 1 and img.C_id == 'C01':
                new_name = os.path.normpath(os.path.join(
                    path, ('{}--{}--{}--{}--C02.ome.tif'.format(
                        img.well, img.E_id, img.field, img.Z_id))))
                img.C_id = 'C02'
            elif img.E_id_int == f_job + 2:
                new_name = os.path.normpath(os.path.join(
                    path, ('{}--{}--{}--{}--C03.ome.tif'.format(
                        img.well, img.E_id, img.field, img.Z_id))))
                img.C_id = 'C03'
            else:
                new_name = img_path
            if not (len(img_array) == 16 or len(img_array) == 256):
                new_paths.append(new_name)
                metadata_d[
                    img.well + '--' + img.field + '--' + img.C_id] = (
                        img.meta_data())
            os.rename(img_path, new_name)
        # Make a max proj per channel and well.
        max_projs = make_proj(new_paths)
        new_dir = os.path.normpath(os.path.join(imdir, 'maxprojs'))
        if not os.path.exists(new_dir):
            os.makedirs(new_dir)
        if img_save:
            print('Saving images')
        if csv_save:
            print('Calculating histograms')
        for C_id, proj in max_projs.iteritems():
            if img_save:
                ptime = time.time()
                p = os.path.normpath(os.path.join(
                    new_dir, 'image--' + img.well + '--' + img.field + '--' +
                    C_id + '.ome.tif'))
                metadata = metadata_d[
                    img.well + '--' + img.field + '--' + C_id]
                # Save meta data and image max proj.
                CamImage(p).save_image(proj, metadata)
                print('Save image:' + str(time.time() - ptime) + ' secs')
            if csv_save:
                ptime = time.time()
                if proj.dtype.name == 'uint8':
                    max_int = 255
                if proj.dtype.name == 'uint16':
                    max_int = 65535
                histo = histogram(proj, 0, max_int, 256)
                rows = defaultdict(list)
                for b, count in enumerate(histo):
                    rows[b].append(count)
                p = os.path.normpath(os.path.join(
                    new_dir, '{}--{}.ome.csv'.format(img.well, C_id)))
                csv = File(p)
                csv.write_csv(rows, ['bin', 'count'])
                print('Save csv:' + str(time.time() - ptime) + ' secs')
        return

    def get_csvs(self, line):
        """Function to find the correct csv files and get their base names."""
        # empty lists for keeping csv file base path names
        # and corresponding well names
        fbs = []
        wells = []
        img = search_imgs(line)
        if img:
            if (img.field == self.last_field and img.C_id == 'C31'):
                if self.end_63x:
                    self.sock.send(self.stop_com)
                ptime = time.time()
                get_imgs(img.well_path, img.well_path, 'E02', img_save=False)
                print(str(time.time() - ptime) + ' secs')
                # get all CSVs and wells
                search = Directory(img.well_path)
                csvs = sorted(search.get_all_files('*.ome.csv'))
                for csv_path in csvs:
                    csv_file = File(csv_path)
                    # Get the filebase from the csv path.
                    fbase = re.sub('C\d\d.+$', '', csv_file.path)
                    #  Get the well from the csv path.
                    well_name = csv_file.get_name('U\d\d--V\d\d')
                    fbs.append(fbase)
                    wells.append(well_name)
        return {'bases': fbs, 'wells': wells}

    def send_com(self, gobj, com_list, end_com_list, stage1=None, stage2=None,
                 stage3=None):
        for com, end_com in zip(com_list, end_com_list):
            # Send CAM list for the gain job to the server during stage1.
            # Send gain change command to server in the four channels
            # during stage2 and stage3.
            # Send CAM list for the experiment jobs to server (stage2/stage3).
            # Reset self.gain_dict for each iteration.
            self.gain_dict = defaultdict(list)
            com = self.del_com + com
            print(com)
            sock.send(com)
            time.sleep(3)
            # Start scan.
            print(self.start_com)
            sock.send(self.start_com)
            time.sleep(7)
            # Start CAM scan.
            print(self.camstart_com)
            sock.send(self.camstart_com)
            time.sleep(3)
            stage4 = True
            while stage4:
                print('Waiting for images...')
                reply = sock.recv_timeout(120, ['image--'])
                for line in reply.splitlines():
                    if stage1 and 'image' in line:
                        print('Stage1')
                        csv_result = self.get_csvs(line)
                        filebases = csv_result['bases']
                        fin_wells = csv_result['wells']
                        self.gain_dict = gobj.calc_gain(filebases, fin_wells)
                        # print(gain_dict) #testing
                        if not self.saved_gains:
                            self.saved_gains = self.gain_dict
                        if self.saved_gains:
                            # print(self.saved_gains) #testing
                            self.saved_gains.update(self.gain_dict)
                            header = ['well', 'green', 'blue', 'yellow', 'red']
                            csv_name = 'output_gains.csv'
                            csv = File(os.path.normpath(
                                os.path.join(self.imaging_dir, csv_name)))
                            csv.write_csv(self.saved_gains, header)
                            gobj.distribute_gain()
                            com_result = gobj.get_com()
                            late_com_list = com_result['com']
                            late_end_com_list = com_result['end_com']
                    elif 'image' in line:
                        if stage2:
                            print('stage2')
                            img_saving = False
                        if stage3:
                            print('stage3')
                            img_saving = True
                        img = self.search_imgs(line)
                        if img:
                            get_imgs(img.field_path,
                                     self.imaging_dir,
                                     img.E_id,
                                     f_job=self.first_job,
                                     img_save=img_saving,
                                     csv_save=False
                                     )
                    if all(test in line for test in end_com):
                        stage4 = False
            # Stop scan
            # print(stop_cam_com)
            # sock.send(stop_cam_com)
            # time.sleep(5)
            print(self.stop_com)
            sock.send(self.stop_com)
            time.sleep(6)  # Wait for it to come to complete stop.
            if self.gain_dict and stage1:
                self.send_com(late_com_list, late_end_com_list, stage1=False,
                              stage2=stage2, stage3=stage3)

    def control(self):
        """Function to control the flow."""
        # #DONE:70 Make sure order of booleans is correct, trello:BST7i275
        # if they effect eachother
        # Booleans etc to control flow.
        stage1 = True
        stage2 = True
        stage3 = False
        if self.end_10x:
            pattern_g = self.pattern_g_10x
            job_list = self.job_10x
            pattern = self.pattern_10x
        elif self.end_40x:
            pattern_g = self.pattern_g_40x
            job_list = self.job_40x
            pattern = self.pattern_40x
        elif self.end_63x:
            stage2 = False
            stage3 = True
            pattern_g = self.pattern_g_63x
            job_list = self.job_63x
            pattern = self.pattern_63x
        if self.coord_file:
            csv = File(self.coord_file)
            coords = csv.read_csv('fov', ['dxPx', 'dyPx'])
        if self.gain_only:
            stage2 = False
            stage3 = False
        if self.input_gain:
            stage1 = False

        # make Gain object
        gobj = Gain(self.gain_dict,
                    self.imaging_dir,
                    self.init_gain,
                    self.r_script,
                    job_list,
                    pattern_g,
                    pattern,
                    self.first_job,
                    self.last_well,
                    end_10x=self.end_10x,
                    end_40x=self.end_40x,
                    end_63x=self.end_63x,
                    template_file=self.template_file,
                    coords=coords
                    )

        # Connect to server
        self.sock.connect(self.host, self.port)

        com_result = gobj.get_init_com()

        # #DONE:30 Finish the control function, trello:wEjYJ3E4

        if self.input_gain:
            csv = File(self.input_gain)
            self.gain_dict = csv.read_csv('well',
                                          ['green', 'blue', 'yellow', 'red'])
            com_result = gobj.get_com()

        com_list = com_result['com']
        end_com_list = com_result['end_com']

        if stage1 or stage2 or stage3:
            self.send_com(com_list, end_com_list, stage1=stage1, stage2=stage2,
                          stage3=stage3)

        print('\nExperiment finished!')
