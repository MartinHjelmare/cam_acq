"""Control the microscope."""
import logging
import os
import re
import time
from collections import defaultdict

import numpy as np
from matrixscreener.cam import CAM
from matrixscreener.experiment import attribute_as_str, attributes, glob

from command import camstart_com, del_com
from gain import Gain
from helper import (find_image_path, find_scan, format_new_name,
                    get_scan_paths, read_csv, rename_imgs, send, write_csv)
from image import make_proj, meta_data, read_image, save_image

_LOGGER = logging.getLogger(__name__)

PATTERN_G_10X = 'pattern7'
PATTERN_G_40X = 'pattern8'
PATTERN_G_63X = 'pattern9'
JOB_10X = ['job22', 'job23', 'job24']
PATTERN_10X = 'pattern10'
JOB_40X = ['job7', 'job8', 'job9']
PATTERN_40X = 'pattern2'
JOB_63X = ['job10', 'job11', 'job12']
PATTERN_63X = 'pattern3'


# #FIXME:20 Function handle_imgs is too complex, trello:hOc4mqsa
def handle_imgs(path, imdir, job_order, f_job=2, img_save=True,
                histo_save=True):
    """Handle acquired images, do renaming, make max projections."""
    scan = find_scan(path)
    # Get all image paths in well or field, depending on path variable.
    imgs = get_scan_paths(scan, 'images', [(job_order, 'E'), path])
    new_paths = []
    metadata_d = {}
    imgp = ''
    for imgp in imgs:
        img_array = read_image(imgp)
        new_name = rename_imgs(scan, imgp, f_job)
        if not (len(img_array) == 16 or len(img_array) == 256):
            new_paths.append(new_name)
            img_attr = attributes(imgp)
            metadata_d['U{}--V{}--X{}--Y{}--C{}'.format(
                img_attr.U, img_attr.V, img_attr.X, img_attr.Y,
                img_attr.C)] = meta_data(imgp)
    # Make a max proj per channel and well.
    max_projs = make_proj(new_paths)
    new_dir = os.path.normpath(os.path.join(imdir, 'maxprojs'))
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
    if img_save:
        _LOGGER.info('Saving images')
    if histo_save:
        _LOGGER.info('Calculating histograms')
    for c_id, proj in max_projs.iteritems():
        if img_save:
            save_path = format_new_name(scan, imgp, root=new_dir,
                                        new_attr={'C': c_id})
            metadata = metadata_d['U{}--V{}--X{}--Y{}--C{}'.format(
                img_attr.U, img_attr.V, img_attr.X, img_attr.Y, img_attr.C)]
            # Save meta data and image max proj.
            save_image(save_path, proj, metadata)
        if histo_save:
            if proj.dtype.name == 'uint8':
                max_int = 255
            if proj.dtype.name == 'uint16':
                max_int = 65535
            histo = np.histogram(proj, 256, (0, max_int))
            rows = defaultdict(list)
            for box, count in enumerate(histo[0]):
                rows[box].append(count)
            save_path = os.path.normpath(os.path.join(
                new_dir, 'U{}--V{}--C{}.ome.csv'.format(
                    img_attr.U, img_attr.V, c_id)))
            write_csv(save_path, rows, ['bin', 'count'])


class Control(object):
    """Represent a control center for the microscope."""

    def __init__(self, args):
        """Set up instance."""
        self.args = args
        self.cam = CAM(self.args.host)
        self.cam.delay = 0.2

        # dicts of lists to store wells with gain values for
        # the four channels.
        self.saved_gains = defaultdict(list)

        # #RFE:0 Assign job vars by config file, trello:UiavT7yP
        # #RFE:10 Assign job vars by parsing the xml/lrp-files, trello:d7eWnJC5

    def get_csvs(self, img_ref):
        """Find correct csv files and get their base names."""
        # empty lists for keeping csv file base path names
        # and corresponding well names
        fbs = []
        wells = []
        path = find_image_path(img_ref, self.args.imaging_dir)
        scan = find_scan(path)
        imgs = get_scan_paths(scan, 'images', [path])
        for imgp in imgs:
            img_attr = attributes(imgp)
            _LOGGER.debug(img_attr)
            if ('X{}--Y{}'.format(img_attr.X, img_attr.Y) ==
                    self.args.last_field and img_attr.c == 31):
                if self.args.end_63x:
                    _LOGGER.debug(self.cam.stop_scan())
                wellp = get_scan_paths(scan, 'wells', [imgp])[0]
                handle_imgs(wellp, wellp, 'E02', img_save=False)
                # get all CSVs and wells
                csvs = glob(wellp + '*.ome.csv')
                for csvp in csvs:
                    csv_attr = attributes(csvp)
                    # Get the filebase from the csv path.
                    fbs.append(re.sub(r'C\d\d.+$', '', csvp))
                    #  Get the well from the csv path.
                    well_name = 'U{}--V{}'.format(csv_attr.U, csv_attr.V)
                    wells.append(well_name)
        return {'bases': fbs, 'wells': wells}

    def save_gain(self, saved_gains):
        """Save a csv file with gain values per image channel."""
        header = ['well', 'green', 'blue', 'yellow', 'red']
        path = os.path.normpath(
            os.path.join(self.args.imaging_dir, 'output_gains.csv'))
        write_csv(path, saved_gains, header)

    # #FIXME:20 Function send_com is too complex, trello:S4Df369p
    def send_com(self, gobj, com_list, end_com_list, stage1=None, stage2=None,
                 stage3=None):
        """Send commands to the CAM server."""
        for com, end_com in zip(com_list, end_com_list):
            # Send CAM list for the gain job to the server during stage1.
            # Send gain change command to server in the four channels
            # during stage2 and stage3.
            # Send CAM list for the experiment jobs to server (stage2/stage3).
            # Reset gain_dict for each iteration.
            gain_dict = defaultdict(list)
            _LOGGER.debug(del_com)
            _LOGGER.debug(self.cam.send(del_com))
            send(self.cam, com)
            time.sleep(3)
            # Start scan.
            _LOGGER.debug(self.cam.start_scan())
            time.sleep(7)
            # Start CAM scan.
            _LOGGER.debug(camstart_com)
            _LOGGER.debug(self.cam.send(camstart_com()))
            time.sleep(3)
            _LOGGER.info('Waiting for images...')
            stage4 = True
            while stage4:
                replies = self.cam.receive()
                if replies is None:
                    time.sleep(0.02)
                    continue
                for reply in replies:
                    if stage1 and reply.get('relpath'):
                        _LOGGER.info('Stage1')
                        _LOGGER.debug(reply)
                        csv_result = self.get_csvs(reply.get('relpath'))
                        _LOGGER.debug(csv_result['bases'])  # testing
                        _LOGGER.debug(csv_result['wells'])  # testing
                        gain_dict = gobj.calc_gain(csv_result)
                        _LOGGER.debug(gain_dict)  # testing
                        self.saved_gains.update(gain_dict)
                        if not self.saved_gains:
                            continue
                        # testing
                        _LOGGER.debug('SAVED_GAINS %s', self.saved_gains)
                        self.save_gain(self.saved_gains)
                        gobj.distribute_gain()
                        com_data = gobj.get_com(
                            self.args.x_fields, self.args.y_fields)
                    elif reply.get('relpath'):
                        if stage2:
                            _LOGGER.info('Stage2')
                            img_saving = False
                        if stage3:
                            _LOGGER.info('Stage3')
                            img_saving = True
                        path = find_image_path(
                            reply['relpath'], self.args.imaging_dir)
                        scan = find_scan(path)
                        imgs = get_scan_paths(scan, 'images', [path])
                        for imgp in imgs:
                            fieldp = get_scan_paths(scan, 'fields', [imgp])[0]
                            handle_imgs(fieldp,
                                        self.args.imaging_dir,
                                        attribute_as_str(imgp, 'E'),
                                        f_job=self.args.first_job,
                                        img_save=img_saving,
                                        histo_save=False)
                    if all(test in reply['relpath'] for test in end_com):
                        stage4 = False
            _LOGGER.debug(self.cam.stop_scan())
            time.sleep(6)  # Wait for it to come to complete stop.
            if gain_dict and stage1:
                self.send_com(gobj, com_data['com'], com_data['end_com'],
                              stage1=False, stage2=stage2, stage3=stage3)

    def control(self):
        """Control the flow."""
        # #DONE:70 Make sure order of booleans is correct, trello:BST7i275
        # if they effect eachother
        # Booleans etc to control flow.
        gain_dict = defaultdict(list)
        stage1 = True
        stage2 = True
        stage3 = False
        if self.args.end_10x:
            pattern_g = PATTERN_G_10X
            job_list = JOB_10X
            pattern = PATTERN_10X
        elif self.args.end_40x:
            pattern_g = PATTERN_G_40X
            job_list = JOB_40X
            pattern = PATTERN_40X
        elif self.args.end_63x:
            stage2 = False
            stage3 = True
            pattern_g = PATTERN_G_63X
            job_list = JOB_63X
            pattern = PATTERN_63X
        if self.args.gain_only:
            stage2 = False
            stage3 = False
        if self.args.input_gain:
            stage1 = False
            gain_dict = read_csv(self.args.input_gain, 'well',
                                 ['green', 'blue', 'yellow', 'red'])

        # make Gain object
        gobj = Gain(self.args, gain_dict, job_list, pattern_g, pattern)

        if self.args.input_gain:
            com_data = gobj.get_com(self.args.x_fields, self.args.y_fields)
        else:
            com_data = gobj.get_init_com()

        if stage1 or stage2 or stage3:
            self.send_com(gobj, com_data['com'], com_data['end_com'],
                          stage1=stage1, stage2=stage2, stage3=stage3)

        _LOGGER.info('\nExperiment finished!')
