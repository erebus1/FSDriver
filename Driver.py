import re
import struct
from File import DFile, Directory, SimpleFile, SymLink
from array import *

__author__ = 'user'


class FileNameOversizing(BaseException):
    pass


class InfinityRecursion(BaseException):
    pass


class WrongDescriptor(BaseException):
    pass


class EmptyDescriptor(BaseException):
    pass


class DescriptorRewriteError(BaseException):
    pass


class WrongDescriptorID(BaseException):
    pass


class Driver:
    class NoFreeBlock(BaseException):
        pass

    class WrongFilePath(BaseException):
        pass


    def read_block_map(self, bin_array, number_of_blocks, block_num=-1):
        """
        extract block map from descriptor, if descriptor has link to another block of hard links, then
        get that block, and continue extracting.
        :param bin_array: block map, last 2 byte - link to next block
        :param number_of_blocks: number of blocks, need to extract
        :return: block_map
        """

        block_map = []
        i = 0

        # parse link from this map
        while number_of_blocks > 0 and i < len(bin_array) - 3:
            block_map.append(bin_array[i] * 256 + bin_array[i + 1])
            i += 2
            number_of_blocks -= 1

        # extract link to another block and continue parsing
        if number_of_blocks > 0:
            block_num = bin_array[i] * 256 + bin_array[i + 1]
            block_num, block_map_temp = self.read_block_map(self.get_block(block_num), number_of_blocks, block_num)
            block_map += block_map_temp

        return block_num, block_map

    def __init__(self):
        self.reset_default()


    def reset_default(self):
        self.number_of_descriptors = 100
        self.size = 32768
        self.block_size = 64
        self.number_of_links_in_descriptor = 5
        self.max_name_length = 15
        self.default_descriptor_number = 1
        self.number_of_blocks = self.size / self.block_size
        self.descriptor_size = self.block_size / 4
        self.cwd = None
        self.FS = None
        self.opened_files = dict()


    def get_block(self, block_num):
        self.FS.seek(block_num * self.block_size)
        str_bytes = self.FS.read(self.block_size)
        bin_array = array('B')
        # convert from string in bytes
        for i in str_bytes:
            bin_array.append(struct.unpack("<B", i)[0])

        return bin_array

    def mount(self, FS):
        bufsize = 0
        try:
            self.FS = file(FS, "rb+", bufsize)
        except:
            print "no such disc"
            self.FS = None
            return
        self.cwd = Directory(self, "/", 1)

    def unmount(self):
        self.FS.close()
        self.reset_default()

    def create_folder_descriptor(self, first_block):
        bin_array = array('B')

        bin_array.append(2)  # type of file 2 - mean folder
        bin_array.append(2)  # number of links to file
        # file size
        bin_array.append(0)
        bin_array.append((self.max_name_length + 1) * 2)  # because it contain only two links
        # map of blocks position
        # first block
        bin_array.append(int(first_block / 256))  # first part of first block
        bin_array.append(first_block % 256)  # second part of first block

        # rest links + link on block with rest links
        bin_array += Driver.zeros_bin_array(self.number_of_links_in_descriptor * 2)
        return bin_array


    def generate_new_FS_bin_array(self):
        """
        generate byte array of empty FS, with just one folder

        """
        bin_array = array('B')

        # bit map
        bin_array.append(255)
        bin_array.append(255)
        bin_array.append(255)
        bin_array.append(int('11100000', 2))
        bin_array += Driver.zeros_bin_array(self.block_size - 4)

        # main folder description
        bin_array += self.create_folder_descriptor(first_block=26)

        # rest empty descriptors
        bin_array += Driver.zeros_bin_array((self.number_of_descriptors - 1) * self.descriptor_size)

        # folder content
        # first link
        bin_array += self.make_hard_link(".", 1)
        # second link
        bin_array += self.make_hard_link("..", 1)
        # end of block
        bin_array += Driver.zeros_bin_array(self.block_size - (self.max_name_length + 1) * 2)

        # rest blocks
        bin_array += Driver.zeros_bin_array((self.number_of_blocks - self.number_of_descriptors / 4 - 2) * 64)

        return bin_array


    def make_hard_link(self, name, descriptor):
        """

        :param name: name of hard link to file
        :param descriptor:  file descriptor
        :return:
        :throws: FileNameOverSizing if file name more than allowed
        :throws: WrongDescriptor if descriptor>255 or >self.number_of_descriptors
        """
        if len(name) > self.max_name_length:
            raise FileNameOversizing
        if descriptor > 255 or descriptor > self.number_of_descriptors:
            raise WrongDescriptor
        bin_array = array('B')
        for i in name:
            bin_array.append(ord(i))
        bin_array += Driver.zeros_bin_array(self.max_name_length - len(name))

        bin_array.append(descriptor)

        return bin_array


    @staticmethod
    def zeros_bin_array(length):
        bin_array = array('B')
        for i in range(length):
            bin_array.append(0)
        return bin_array


    def create_new_FS(self, filename):
        fs = open(filename, "wb")
        bin_array = self.generate_new_FS_bin_array()
        bin_array.tofile(fs)
        fs.close()

    def pwd(self):
        if self.FS is None:
            print "no disc"
            return
        if self.cwd is not None:
            print(self.cwd.path)
        else:
            print("no disk")

    def file_stat(self, id):
        if self.FS is None:
            print "no disc"
            return
        if id > self.number_of_descriptors or id < 1:
            print("wrong descriptor number")
            return

        block_id = int((id - 1) / 4) + 1  # calc number of block
        try:
            file = DFile(self, "", id)
        except DFile.EmptyDescriptor:
            print("empty descriptor")
            return

        print(file.get_descriptor_prop())

    def ls(self):
        if self.FS is None:
            print "no disc"
            return
        self.cwd = Directory(self, self.cwd.path, self.cwd.descriptor_id)
        if self.cwd is not None:
            links = self.cwd.ls()
            print(links)
        else:
            print("no disk")

    def rewrite_descriptor(self, descriptor_id, bin_array):
        """
        rewrite block with specified descriptor
        :param descriptor_id:
        :param bin_array: new file descriptor
        :return: None
        """
        if len(bin_array) != self.descriptor_size:
            raise DescriptorRewriteError
        if descriptor_id < 1:
            raise WrongDescriptorID

        block_id = int((descriptor_id - 1) / 4) + 1  # calc number of block
        descriptor = self.get_block(block_id)  # get this block

        shift = ((descriptor_id - 1) % 4) * self.descriptor_size  # calc shift in block
        descriptor[shift:shift + self.descriptor_size] = bin_array

        self.FS.seek(block_id * self.block_size)
        self.FS.write(descriptor)

    def rewrite_block(self, block_id, bin_array):
        if block_id < 0 or block_id > self.size / self.block_size:
            print("wrong block_id")
            return
        if len(bin_array) != self.block_size:
            print("wrong block")
            return

        self.FS.seek(block_id * self.block_size)
        self.FS.write(bin_array)


    def create(self, filepath):
        """
        create descriptor for file and rewrite it.
        create link on file in cwd
        :param filepath:
        :return:
        """
        if self.FS is None:
            print "no disc"
            return
        descriptor_id = self.get_free_descriptor_id()
        if descriptor_id < 1:
            print "no free descriptors"
            return

        parent_directory, filename = self.parse_path(filepath)
        if self.get_descriptor_by_name(parent_directory, filename):
            print("this name already exist")
            return
        try:
            parent_directory.add_link(descriptor_id, filename)
        except Driver.NoFreeBlock:
            print ("no free space for creating link")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return


        bin_array = self.create_file_descriptor()
        self.rewrite_descriptor(descriptor_id, bin_array)


    def create_file_descriptor(self):
        """

        :return: bin_array of new file descriptor
        """
        bin_array = array('B')

        bin_array.append(1)  # type of file 1 - mean file
        bin_array.append(1)  # number of links to file
        # file size
        bin_array.append(0)
        bin_array.append(0)  # empty file

        # map of blocks position
        # all links + link on block with rest links = zero
        bin_array += Driver.zeros_bin_array((self.number_of_links_in_descriptor + 1) * 2)
        return bin_array

    def get_free_descriptor_id(self):
        """

        :return: first empty descriptor id or -1 if no free descriptors

        """
        descriptor_id = 0
        for k in range(1, self.number_of_descriptors / 4):  # go through all blocks with descriptors
            descriptors = self.get_block(k)
            for i in range(0, len(descriptors), self.descriptor_size):  # go though all descriptors in block
                descriptor_id += 1
                try:
                    DFile(self, "", descriptor_id)
                except DFile.EmptyDescriptor:
                    return descriptor_id
        return -1


    def get_free_block_id(self):
        """

        :return: number of first empty block
        """
        block_num = 0
        block = self.get_block(0)
        for i in range(len(block)):
            bits = bin(block[i])[2:]
            if len(bits) < 8:
                block[i] += 128
                self.rewrite_block(0, block)
                return block_num

            for k in range(8):
                if bits[k] == '0':
                    bits = list(bits)
                    bits[k] = '1'
                    bits = "".join(bits)
                    block[i] = int(bits, 2)
                    self.rewrite_block(0, block)
                    return block_num
                block_num += 1

        raise Driver.NoFreeBlock

    def free_block(self, block_id):
        """
        set that block with block id is empty
        :param block_id:
        :return:
        """
        byte = block_id / 8
        bit = block_id % 8

        template = "11111111"
        template = list(template)
        template[bit] = "0"
        template = "".join(template)
        template = int(template, 2)

        block = self.get_block(0)
        block[byte] &= template

        self.rewrite_block(0, block)


    def get_descriptor(self, descriptor_id):
        block_id = int((descriptor_id - 1) / 4) + 1  # calc number of block
        shift = ((descriptor_id - 1) % 4) * self.descriptor_size  # calc shift in block
        return block_id, shift


    def check_path_template(self, filepath):  # check on template
        if filepath == "/":
            return True
        check_template = re.compile(r'/?[\w\.]+(/[\w\.]+)*/?')

        return check_template.match(filepath) and check_template.match(filepath).group() == filepath

    def unwrap_filepath(self, parent_directory, path):
        """

        :param parent_directory:
        :param path: list of file (directory/symlink) names
        :return: new parent directory
        :raise Driver.WrongFilePath, Infinity Recursions
        """
        template = re.compile(r'[\w\.]+/')

        max_items_in_path = 100
        cur_iter = 0
        while len(path) > 0 and cur_iter < max_items_in_path:
            cur_iter += 1
            next_directory_name = path.pop(0)
            next_descriptor_id = self.get_descriptor_by_name(parent_directory, next_directory_name[:-1])
            if not next_descriptor_id:
                raise Driver.WrongFilePath
            file = DFile(self, "", next_descriptor_id)
            if file.file_type == 1:
                raise Driver.WrongFilePath
            elif file.file_type == 2:
                if next_descriptor_id != parent_directory.descriptor_id:
                    parent_directory = Directory(self, parent_directory.path + next_directory_name, next_descriptor_id)
            elif file.file_type == 3:
                symlink = SymLink(self, "", next_descriptor_id)
                symlink_path = symlink.get_link()
                if symlink_path[0] == "/":
                    parent_directory = Directory(self, "/", 1)
                    symlink_path = symlink_path[1:]
                additional_path = template.findall(symlink_path)
                path = additional_path + path

        if cur_iter >= max_items_in_path:
            raise InfinityRecursion

        return parent_directory

    def parse_path(self, filepath, last_unwrap=True, cur_iter=0, start_directory=None):
        if cur_iter > 100:
            raise InfinityRecursion
        cur_iter += 1
        if start_directory is None:
            start_directory = self.cwd

        filepath = filepath.strip()  # remove start and end whitespaces
        if filepath == "/":
            parent_directory = Directory(self, self.cwd.path, self.cwd.descriptor_id)
            filename = "."
            return parent_directory, filename

        if not self.check_path_template(filepath):
            raise Driver.WrongFilePath

        if filepath[0] == "/":
            parent_directory = Directory(self, "/", 1)  # start from root directory
            filepath = filepath[1:]  # remove '/' from the end
        else:
            # start from current directory or specified directory
            parent_directory = Directory(self, start_directory.path, start_directory.descriptor_id)

        if filepath[-1] == "/":
            filepath = filepath[:-1]  # remove '/' from the end


        # filepath = (.../)*...
        template = re.compile(r'[\w\.]+/')
        path = template.findall(filepath)  # get all middle path items
        parent_directory = self.unwrap_filepath(parent_directory, path)

        pos = filepath.rfind("/")  # extract file name
        if pos >= 0:
            filename = filepath[pos+1:]
        else:
            filename = filepath

        if last_unwrap:  # if we should unwrap last item of file path
            filename_descriptor_id = self.get_descriptor_by_name(parent_directory, filename)
            if not filename_descriptor_id:
                return parent_directory, filename
            try:
                symlink = SymLink(self, "", filename_descriptor_id)
                symlink_path = symlink.get_link()
                parent_directory, filename = self.parse_path(symlink_path, True, cur_iter, parent_directory)

            except DFile.NonSymLink:
                if filename == "..":
                    parent_directory = self.go_up(parent_directory)
                    filename = "."
                return parent_directory, filename

        if filename == "..":
                    parent_directory = self.go_up(parent_directory)
                    filename = "."
        return parent_directory, filename

    def go_up(self, parent_directory):
        descriptor_id = self.get_descriptor_by_name(parent_directory, "..")
        path = parent_directory.path
        if len(path) > 1:
            path = path[:-1]  # path without '/' at the end
            pos = path.rfind("/")
            path = path[:pos] + "/"
        parent_directory = Directory(self, path, descriptor_id)
        return parent_directory
    def get_descriptor_by_name(self, directory, filename):
        """
        check has directory link with this filename
        :param directory:
        :param filename:
        :return: descriptor_id if has, else false (0)
        """
        links = directory.ls()
        if filename in links.keys() and links[filename] > 0:
            return links[filename]
        return False


    def open(self, filepath):
        if self.FS is None:
            print "no disc"
            return
        try:
            parent_directory, filename = self.parse_path(filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return

        descriptor_id = self.get_descriptor_by_name(parent_directory, filename)
        if descriptor_id == 0:
            print("no such file")
            return

        try:
            simple_file = SimpleFile(self, parent_directory.path + filename, descriptor_id)
        except DFile.NonSimpleFile:
            print("can not apply for non simple file")
            return


        # first, search in opened files
        for key in self.opened_files.keys():
            if self.opened_files[key].descriptor_id == simple_file.descriptor_id:
                print("File has already opened with id: " + str(key))
                return key

        # if this file hasn't been opened yet, set key, and add to opened_files
        if len(self.opened_files.keys()) == 0:
            key = 1
        else:
            key = max(self.opened_files.keys()) + 1
        self.opened_files[key] = simple_file

        print("File opened, file id: " + str(key))
        return key

    def print_opened(self):
        if self.FS is None:
            print "no disc"
            return
        print("fd, descriptor_id, path:")
        for key in self.opened_files:
            print(key, self.opened_files[key].descriptor_id, self.opened_files[key].path)

    def close(self, fd):
        if self.FS is None:
            print "no disc"
            return
        for key in self.opened_files.keys():
            if key == fd:
                self.opened_files[key].close()
                self.opened_files.__delitem__(key)
                print("file closed")
                return
        print("no such fd")

    def write(self, fd, shift, message):
        if self.FS is None:
            print "no disc"
            return
        if fd not in self.opened_files.keys():
            print "no opened file with such fd"
            return

        # update information
        self.opened_files[fd] = SimpleFile(self, self.opened_files[fd].path, self.opened_files[fd].descriptor_id)
        try:
            self.opened_files[fd].write(shift, message)
        except Driver.NoFreeBlock:
            print("no enough free space")
        except DFile.WrongShift:
            print("wrong shift")

    def read(self, fd, shift, size):
        if self.FS is None:
            print "no disc"
            return
        if fd not in self.opened_files.keys():
            print "no opened file with such fd"
            return

        # update information
        self.opened_files[fd] = SimpleFile(self, self.opened_files[fd].path, self.opened_files[fd].descriptor_id)
        try:
            res = self.opened_files[fd].read(shift, size)
        except DFile.WrongShift:
            print "wrong shift or size"
            return

        print res

    def get_number_of_free_blocks(self):
        """

        :return: number of free blocks
        """

        free_block_num = 0
        block = self.get_block(0)
        for i in range(len(block)):
            bits = bin(block[i])[2:]
            free_block_num += 8 - len(bits)
            for k in bits:
                if k == '0':
                    free_block_num += 1

        return free_block_num

    def link(self, exist_filepath, new_filepath):
        """
        make link on exist_filepath from new_filepath
        increase number of links on file
        only for simple files
        :param exist_filepath:
        :param new_filepath:
        :return:
        """
        if self.FS is None:
            print "no disc"
            return
        try:
            parent_directory_of_exist_file, exist_filename = self.parse_path(exist_filepath)
            parent_directory_of_new_file, new_filename = self.parse_path(new_filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return

        if self.get_descriptor_by_name(parent_directory_of_new_file, new_filename):
            print(new_filepath + " already exist")
            return

        descriptor_id = self.get_descriptor_by_name(parent_directory_of_exist_file, exist_filename)
        if descriptor_id == 0:
            print("no such file: " + exist_filepath)
            return

        try:
            simple_file = SimpleFile(self, parent_directory_of_exist_file.path + exist_filename, descriptor_id)
        except DFile.NonSimpleFile:
            print("can not apply for non simple file")
            return

        try:
            parent_directory_of_new_file.add_link(descriptor_id, new_filename)
        except Driver.NoFreeBlock:
            print "no enough free space"
            return

        simple_file.increase_number_of_links_on_file()

    def unlink(self, filepath):
        """
        delete link by filepath,
        decrease number of links on file
        if file has no more links, then delete file
        :param filepath:
        :return:
        """
        if self.FS is None:
            print "no disc"
            return

        try:
            parent_directory, filename = self.parse_path(filepath, last_unwrap=False)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return

        descriptor_id = self.get_descriptor_by_name(parent_directory, filename)
        if not descriptor_id:
            print("no such link")
            return

        cur_file = DFile(self, parent_directory.path + filename, descriptor_id)
        if cur_file.file_type == 2:
            print "cannot remove link on directory"
            return

        parent_directory.remove_link(filename)

        cur_file.decrease_number_of_links_on_file()  # if there is no more links, then delete file

    def truncate(self, filepath, size):
        if self.FS is None:
            print "no disc"
            return
        try:
            parent_directory, filename = self.parse_path(filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return

        descriptor_id = self.get_descriptor_by_name(parent_directory, filename)
        if descriptor_id == 0:
            print("no such file")
            return

        try:
            simple_file = SimpleFile(self, parent_directory.path + filename, descriptor_id)
        except DFile.NonSimpleFile:
            print("can not apply for non simple file")
            return

        try:
            simple_file.truncate(size)
        except Driver.NoFreeBlock:
            print "no enough free space"

    def mkdir(self, filepath):
        if self.FS is None:
            print "no disc"
            return
        try:
            parent_directory, filename = self.parse_path(filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return

        if self.get_descriptor_by_name(parent_directory, filename):
            print "this file already exist"
            return

        try:
            parent_directory.create_directory(filename)
        except DFile.DuplicatedName:
            print "this file already exist"
        except Driver.NoFreeBlock:
            print "no free space"
        except DFile.NoFreeDescriptors:
            print "no free descriptors"


    def rmdir(self, filepath):
        if self.FS is None:
            print "no disc"
            return
        try:
            parent_directory, filename = self.parse_path(filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return

        descriptor_id = self.get_descriptor_by_name(parent_directory, filename)
        if descriptor_id == 0:
            print("no such folder")
            return

        directory = Directory(self, parent_directory.path + filename, descriptor_id)

        # check is directory empty?
        links = directory.ls()
        for key in links.keys():
            if key != "." and key != "..":
                print "error: non empty directory"
                return
        try:
            parent_directory.remove_link(filename)
        except DFile.CannotDelete:
            print "can not delete"
            return

        directory.self_destruction()

    def cd(self, filepath="/"):
        if self.FS is None:
            print "no disc"
            return
        try:
            parent_directory, filename = self.parse_path(filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return


        descriptor_id = self.get_descriptor_by_name(parent_directory, filename)
        if descriptor_id == 0:
            print("no such folder")
            return

        pathx = parent_directory.path + filename + "/"
        if filename == ".":
            pathx = parent_directory.path


        try:
            directory = Directory(self, pathx , descriptor_id)
        except DFile.NonDirectory:
            print(filepath + " :not a directory file")
            return

        self.cwd = directory
        print "current directory: "+self.cwd.path


    def symlink(self, filepath, link_filepath):
        """

        :param filepath: file path which will be in symlink
        :param link_filepath: symlink filepath
        :return:
        """
        if self.FS is None:
            print "no disc"
            return

        filepath = filepath.strip()  # remove start and end whitespaces
        if not self.check_path_template(filepath):
            print "wrong path of content"
            return

        try:
            parent_directory_of_link, link_filename = self.parse_path(link_filepath)
        except Driver.WrongFilePath:
            print("wrong path")
            return
        except InfinityRecursion:
            print "infinity recursion"
            return


        if self.get_descriptor_by_name(parent_directory_of_link, link_filename):
            print(link_filepath + " already exist")
            return

        try:
            parent_directory_of_link.create_symlinlk(link_filename, filepath)
        except DFile.DuplicatedName:
            print "this file already exist"
        except Driver.NoFreeBlock:
            print "no free space"
        except DFile.NoFreeDescriptors:
            print "no free descriptors"



