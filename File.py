from collections import OrderedDict
import Driver

__author__ = 'user'
from array import *
import math


class DFile(object):
    class DuplicatedName(BaseException):
        pass

    class CannotDelete(BaseException):
        pass

    class NoFreeDescriptors(BaseException):
        pass

    class Error(BaseException):
        pass

    class WrongShift(BaseException):
        pass

    class NonSimpleFile(BaseException):
        pass

    class NonDirectory(BaseException):
        pass

    class NonSymLink(BaseException):
        pass

    class AddingBlockError(BaseException):
        pass

    class WrongDescriptor(BaseException):
        pass

    class EmptyDescriptor(BaseException):
        pass

    def __init__(self, driver, path, descriptor_id):
        bin_array = DFile.get_bin_array(descriptor_id, driver)
        self.descriptor_id = descriptor_id
        self.file_type = bin_array[0]
        if self.file_type == 0:
            raise DFile.EmptyDescriptor
        self.path = path
        self.driver = driver
        self.number_of_links_on_file = bin_array[1]
        self.size = bin_array[2] * 256 + bin_array[3]

        # calc number of links for blocks of this file
        number_of_blocks = self.size / self.driver.block_size
        if self.size % self.driver.block_size > 0:
            number_of_blocks += 1

        # extract block_map
        self.last_block_num_of_block_map, self.block_map = driver.read_block_map(
            bin_array[4:2 * (driver.number_of_links_in_descriptor + 1) + 4],
            number_of_blocks)
        pass

    def get_descriptor_prop(self):
        if self.file_type == 1:
            type = "simple file"
        elif self.file_type == 2:
            type = "directory"
        elif self.file_type == 3:
            type = "symlink"
        else:
            raise DFile.WrongDescriptor

        res = "type = " + type + "\n"
        res += "number of links on file = " + str(self.number_of_links_on_file) + "\n"
        res += "size = " + str(self.size) + "\n"
        res += "block map: " + str(self.block_map) + "\n"

        return res

    def add_new_block_id_in_descriptor(self, new_block_id):
        """
        add new_block_id in the descriptor list of direct links
        :param new_block_id:
        :return:
        """
        if len(self.block_map) >= self.driver.number_of_links_in_descriptor:
            raise DFile.AddingBlockError

        # get descriptor
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        descriptor = self.driver.get_block(block_id)
        shift += 4 + len(self.block_map) * 2

        # rewrite descriptor
        descriptor[shift] = new_block_id / 256
        descriptor[shift + 1] = new_block_id % 256
        self.driver.rewrite_block(block_id, descriptor)

    def add_link_on_new_block_with_direct_links_in_descriptor(self, block_for_blocks_id_id):
        """
        if there is no free space to add direct link in descriptor,
        then add link to the new block with directs links in the end of descriptor
        :param block_for_blocks_id_id: new block with directs links id
        :return:
        """
        if len(self.block_map) != self.driver.number_of_links_in_descriptor:
            raise DFile.AddingBlockError

        # get descriptor
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        block = self.driver.get_block(block_id)

        # add link in the descriptor to the block of direct links
        block[shift + self.driver.descriptor_size - 2] = int(block_for_blocks_id_id / 256)
        block[shift + self.driver.descriptor_size - 1] = int(block_for_blocks_id_id % 256)

        # save changes on disc
        self.driver.rewrite_block(block_id, block)

        # change last block number of block map
        self.last_block_num_of_block_map = block_for_blocks_id_id

    def add_new_block_id_in_last_block(self, new_block_id, pos):
        """
        if there is free space in last block of direct links, then add link on new_block there
        :param new_block_id:
        :param pos: pos of adding (number of link)
        :return:
        """
        if len(self.block_map) < self.driver.number_of_links_in_descriptor:
            raise DFile.AddingBlockError

        # get block
        last_block = self.driver.get_block(self.last_block_num_of_block_map)

        # add link
        last_block[pos * 2] = int(new_block_id / 256)
        last_block[pos * 2 + 1] = new_block_id % 256

        # save changes on disc
        self.driver.rewrite_block(self.last_block_num_of_block_map, last_block)

    def add_new_block_id(self, new_block_id):
        """
        add new_block_id in block map and modify fs
        :param new_block_id:
        :return:
        """
        # if there is free space in descriptor
        if len(self.block_map) < self.driver.number_of_links_in_descriptor:
            self.add_new_block_id_in_descriptor(new_block_id)

        # if we need add link in descriptor on new block with direct links
        elif len(self.block_map) == self.driver.number_of_links_in_descriptor:
            block_for_blocks_id_id = self.driver.get_free_block_id()  # get id of new block of direct links
            # print("block for links: " + str(block_for_blocks_id_id))
            self.add_link_on_new_block_with_direct_links_in_descriptor(block_for_blocks_id_id)

            self.add_new_block_id_in_last_block(new_block_id, pos=0)  # add link in the beginning of last block

        else:  # if there is no free space in descriptor
            num_of_links_in_block = self.driver.block_size / 2 - 1
            number_of_links_in_last_block = (len(
                self.block_map) - self.driver.number_of_links_in_descriptor) % num_of_links_in_block
            # if there is free space in last block
            if number_of_links_in_last_block > 0:  # if 0, then block is full
                self.add_new_block_id_in_last_block(new_block_id, number_of_links_in_last_block)
            else:  # if there is no free space in last block
                block_for_blocks_id_id = self.driver.get_free_block_id()  # get id of new block for direct links
                # print("block for links: " + str(block_for_blocks_id_id))
                # add link to new block with direct links in the end of last block
                self.add_new_block_id_in_last_block(block_for_blocks_id_id, pos=num_of_links_in_block)
                # change last block number
                self.last_block_num_of_block_map = block_for_blocks_id_id

                self.add_new_block_id_in_last_block(new_block_id, pos=0)

        self.block_map.append(new_block_id)  # add block to the block map

    def is_simple_file(self):
        if self.file_type == 1:
            return True
        return False

    def rewrite_size(self):
        """
        rewrite size of file
        :return:
        """
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        descriptor = self.driver.get_block(block_id)
        descriptor[shift + 2] = self.size / 256
        descriptor[shift + 3] = self.size % 256
        self.driver.rewrite_block(block_id, descriptor)

    def write(self, shift, message):
        bin_array = DFile.str_to_bin(message)
        self.write_bin_array(shift, bin_array)

    @staticmethod
    def get_bin_array(descriptor_id, driver):
        block_id, shift = driver.get_descriptor(descriptor_id)
        bin_array = driver.get_block(block_id)[shift:shift + driver.descriptor_size]
        return bin_array

    @staticmethod
    def bin_to_str(bin_array):
        """
        convert byte array in string such way:
            if byte == 0 -> skip it, else add to result chr(byte)
        :param bin_array -array of byte, that we should convert in string
        :return String
        """
        res = ""
        for i in bin_array:
            if i == 0:
                continue
            res += chr(i)
        return res

    @staticmethod
    def str_to_bin(message):
        """
        convert string message in byte array
        :param message
        :return bin_array
        """
        res = array('B')
        for i in message:
            res.append(ord(i))
        return res

    def add_blocks(self, number_of_additional_blocks):
        """
        reserve new blocks and add link for them in file' block map
        :param number_of_additional_blocks: how many blocks should we add
        :return:
        """
        # if there are no enough blocks for adding and for storing new links, raise exception
        if self.driver.get_number_of_free_blocks() < number_of_additional_blocks * (1 + 1.0 / 32):
            raise Driver.Driver.NoFreeBlock

        for i in range(number_of_additional_blocks):
            block_id = self.driver.get_free_block_id()
            self.add_new_block_id(block_id)

    def write_in_block(self, block_id, shift, bin_array):
        """
        rewrite information in block with block_id id
        :param block_id:
        :param shift:
        :param bin_array:
        :return:
        """
        # check for enough free space
        free_size = self.driver.block_size - shift
        if free_size < len(bin_array):
            raise DFile.Error

        # get block
        block = self.driver.get_block(block_id)
        # modify block
        block[shift:shift + len(bin_array)] = bin_array
        # rewrite block
        self.driver.rewrite_block(block_id, block)

    def write_bin_array(self, global_shift, bin_array):
        """
        Write bin array in file, used by simple file and symlinks
        :param global_shift: shift relative to the beg of file
        :param bin_array:
        :return:
        :raise DFile.NoFreeBlocks, if no enough space
        """
        message_size = len(bin_array)
        free_size = self.size - global_shift

        if free_size < 0 or global_shift < 0:
            raise DFile.WrongShift

        # add enough number of blocks
        if free_size < message_size:
            number_of_useful_blocks = int(math.ceil(float(global_shift + message_size) / self.driver.block_size))
            number_of_additional_blocks = number_of_useful_blocks - len(self.block_map)
            self.add_blocks(number_of_additional_blocks)

        # change file_size
        new_size = max(self.size, global_shift + message_size)
        if new_size != self.size:
            self.size = new_size
            self.rewrite_size()

        shift = global_shift % self.driver.block_size  # calc shift in first lock
        block_map_id = global_shift / self.driver.block_size  # calc first block
        block_size = self.driver.block_size

        # write information in blocks
        while len(bin_array) > 0:
            self.write_in_block(self.block_map[block_map_id], shift, bin_array[:block_size - shift])
            bin_array = bin_array[block_size - shift:]
            block_map_id += 1
            shift = 0

    def read_bin_array(self, shift, size):
        """
        Read bin array from file, used by simple file and symlinks
        :param shift:
        :param size:
        :return:
        """
        size = min(self.size - shift, size)

        if size < 0 or shift < 0:
            raise DFile.WrongShift

        shift = shift % self.driver.block_size  # calc shift in first lock
        block_map_id = shift / self.driver.block_size  # calc first block
        block_size = self.driver.block_size

        bin_array = array('B')
        # read information from blocks
        while size > 0:
            bin_array += self.read_from_block(self.block_map[block_map_id], shift, min(size, block_size - shift))
            size -= block_size - shift
            block_map_id += 1
            shift = 0

        return bin_array

    def read_from_block(self, block_id, shift, size):
        """
        read information from block with block_id id
        :param block_id:
        :param shift:
        :param size:
        :return:
        """
        # check for enough space
        exist_size = self.driver.block_size - shift
        if exist_size < size:
            raise DFile.Error

        # get block
        block = self.driver.get_block(block_id)
        return block[shift:shift + size]

    def increase_number_of_links_on_file(self):
        """
        increase and rewrite number of links on file
        :return:
        """
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        descriptor = self.driver.get_block(block_id)
        descriptor[shift + 1] += 1
        self.driver.rewrite_block(block_id, descriptor)
        self.number_of_links_on_file += 1

    def decrease_number_of_links_on_file(self):
        """
        decrease and rewrite number of links on file
        :return:
        """
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        descriptor = self.driver.get_block(block_id)
        descriptor[shift + 1] -= 1
        self.driver.rewrite_block(block_id, descriptor)
        self.number_of_links_on_file -= 1

        if self.number_of_links_on_file <= 0:
            self.self_destruction()

    def self_destruction(self):
        # free blocks with data
        for i in self.block_map:
            self.driver.free_block(i)

        self.free_blocks_with_direct_links()

        self.free_descriptor()


    def free_blocks_with_direct_links(self):
        """
        delete blocks with direct links on file blocks
        """
        number_of_blocks = \
            int(math.ceil(float(len(self.block_map) - self.driver.number_of_links_in_descriptor) / 31))
        if number_of_blocks <= 0:
            return

        block_id = self.extract_id_from_descriptor()
        self.driver.free_block(block_id)
        number_of_blocks -= 1

        while number_of_blocks > 0:
            a, b = self.driver.get_block(block_id)[-2:]  # get link to the next block
            block_id = a * 256 + b
            self.driver.free_block(block_id)
            number_of_blocks -= 1


    def extract_id_from_descriptor(self):
        """

        :return: block id with direct links on part of file
        """
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        shift += 4 + self.driver.number_of_links_in_descriptor * 2
        descriptor = self.driver.get_block(block_id)
        a, b = descriptor[shift:shift + 2]
        block_id = a * 256 + b
        return block_id


    def free_descriptor(self):
        block_id, shift = self.driver.get_descriptor(self.descriptor_id)
        descriptor = self.driver.get_block(block_id)
        descriptor[shift:shift + self.driver.descriptor_size] = \
            self.driver.zeros_bin_array(self.driver.descriptor_size)
        self.driver.rewrite_block(block_id, descriptor)


class Directory(DFile):
    def __init__(self, driver, path, descriptor_id):
        super(Directory, self).__init__(driver, path, descriptor_id)
        if self.file_type != 2:
            raise DFile.NonDirectory

    def ls(self):
        res_links = dict()
        size_left = self.size
        for block_num in self.block_map:
            block = self.driver.get_block(block_num)

            links = self.extract_hard_links(block, size_left)
            for link in links.keys():
                if links[link] > 0:  # not include empty links
                    res_links[link] = links[link]
            size_left -= self.driver.block_size
        return res_links


    def extract_hard_links(self, bin_array, size_left):
        size_left = min(len(bin_array), size_left)
        links = OrderedDict()
        link_size = self.driver.max_name_length + 1
        for i in range(0, size_left, link_size):
            file_name = Directory.bin_to_str(bin_array[i:i + self.driver.max_name_length])
            descriptor = bin_array[i + self.driver.max_name_length]
            links[file_name] = descriptor

        return links


    def add_link(self, descriptor_id, filename):
        """

        :param descriptor_id:
        :param filename:
        :return:
        :raise Driver.NoFreeBlock
        """
        if self.try_to_add_in_empty_link(descriptor_id, filename):
            return

        # add new block to block map, if necessary
        if self.size % self.driver.block_size < self.driver.max_name_length + 1:  # if no free space in exist blocks
            block_id = self.driver.get_free_block_id()
            self.add_new_block_id(block_id)

        # compute and get block for adding inf
        block_id = self.block_map[-1]
        block = self.driver.get_block(block_id)
        block_shift = self.size % self.driver.block_size  # todo if block_size % link_size != 0
        link_size = self.driver.max_name_length + 1

        # add link
        block[block_shift:block_shift + link_size] = self.driver.make_hard_link(filename, descriptor_id)

        self.driver.rewrite_block(block_id, block)

        self.size += self.driver.max_name_length + 1

        self.rewrite_size()

    def try_to_add_in_empty_link(self, descriptor_id, filename):
        """
        go through all links, and if there are some empty links, then write in it specified information
        :param descriptor_id:
        :param filename:
        :return: True, if information added, otherwise false
        """
        size_left = self.size
        for block_num in self.block_map:
            block = self.driver.get_block(block_num)

            links = self.extract_hard_links(block, size_left)
            pos = 0
            for link in links.keys():
                if links[link] <= 0:
                    self.rewrite_link(block_num, pos, self.driver.make_hard_link(filename, descriptor_id))
                    return True
                pos += 1
            size_left -= self.driver.block_size
        return False

    def rewrite_link(self, block_id, pos, hard_link):
        """
        rewrite link in file
        :return:
        """
        block = self.driver.get_block(block_id)
        shift = pos * (self.driver.max_name_length + 1)
        block[shift:shift + self.driver.max_name_length + 1] = hard_link
        self.driver.rewrite_block(block_id, block)

    def remove_link(self, filename):
        """
        go through all links, and find link with filename name, then set its' descriptor = -1
        :param filename:
        :return True if deleted, otherwise False
        """
        if filename == "." or filename == "..":
            raise DFile.CannotDelete
        size_left = self.size
        for block_num in self.block_map:
            block = self.driver.get_block(block_num)

            links = self.extract_hard_links(block, size_left)
            pos = 0
            for link in links.keys():
                if link == filename and links[link] > 0:
                    self.rewrite_link(block_num, pos, self.driver.make_hard_link("", 0))
                    return True
                pos += 1
            size_left -= self.driver.block_size
        return False

    def create_directory(self, filename):
        """

        :param filename:
        :return:
        :raise DFile.NoFreeDescriptors, Driver.NoFreeBlocks, DFile.DuplicatedName
        """
        data_block_id = self.driver.get_free_block_id()  # get block for data (hard links)
        bin_array = self.driver.create_folder_descriptor(data_block_id)  # get folder template
        descriptor_id = self.driver.get_free_descriptor_id()
        if descriptor_id < 0:
            raise DFile.NoFreeDescriptors

        # rewrite descriptor
        descriptor_block_id, shift = self.driver.get_descriptor(descriptor_id)

        descriptor = self.driver.get_block(descriptor_block_id)
        descriptor[shift: shift + self.driver.descriptor_size] = bin_array
        self.driver.rewrite_block(descriptor_block_id, descriptor)

        # add links
        data = self.driver.get_block(data_block_id)
        link1 = self.driver.make_hard_link(".", descriptor_id)
        link2 = self.driver.make_hard_link("..", self.descriptor_id)
        data[:(self.driver.max_name_length + 1) * 2] = link1 + link2
        self.driver.rewrite_block(data_block_id, data)

        # add hard link on this folder
        self.add_link(descriptor_id, filename)

    def create_symlinlk(self, link_filename, filepath):
        """
        :param link_filename:
        :param filepath:
        :return:
        :raise DFile.NoFreeDescriptors, Driver.NoFreeBlocks, DFile.DuplicatedName
        """
        number_of_useful_blocks = math.ceil(float(len(filepath)) / self.driver.block_size) * (1 + 1 / 32.0)
        if number_of_useful_blocks > self.driver.get_number_of_free_blocks():
            raise Driver.Driver.NoFreeBlock

        bin_array = self.driver.create_file_descriptor()  # get file template
        bin_array[0] = 3  # set type as symlink
        descriptor_id = self.driver.get_free_descriptor_id()
        if descriptor_id < 0:
            raise DFile.NoFreeDescriptors

        # rewrite descriptor
        descriptor_block_id, shift = self.driver.get_descriptor(descriptor_id)

        descriptor = self.driver.get_block(descriptor_block_id)
        descriptor[shift: shift + self.driver.descriptor_size] = bin_array
        self.driver.rewrite_block(descriptor_block_id, descriptor)

        # add data
        symlink = SymLink(self.driver, "", descriptor_id)
        symlink.write(0, filepath)

        # add hard link on this folder
        self.add_link(descriptor_id, link_filename)


class SimpleFile(DFile):
    def __init__(self, driver, path, descriptor_id):
        super(SimpleFile, self).__init__(driver, path, descriptor_id)
        if self.file_type != 1:
            raise DFile.NonSimpleFile

    def close(self):
        """
        save something unsaved on disc
        :return:
        """
        pass


    def read(self, shift, size):
        bin_array = self.read_bin_array(shift, size)
        return self.bin_to_str(bin_array)

    def truncate(self, new_size):
        if self.size == new_size:
            pass
        elif self.size > new_size:
            self.decrease_size(new_size)
        else:
            self.write_bin_array(self.size, self.driver.zeros_bin_array(new_size - self.size))


    def decrease_size(self, new_size):
        if new_size >= self.size:
            raise DFile.Error

        # calc new number of blocks
        number_useful_blocks = int(math.ceil(float(new_size) / self.driver.block_size))
        number_of_blocks_to_free = len(self.block_map) - number_useful_blocks

        # free unuseful blocks and get them out from block_map
        while number_of_blocks_to_free > 0:
            number_of_blocks_to_free -= 1
            self.driver.free_block(self.block_map.pop())

        self.size = new_size
        self.rewrite_size()  # rewrite file size


class SymLink(DFile):
    def __init__(self, driver, path, descriptor_id):
        super(SymLink, self).__init__(driver, path, descriptor_id)
        if self.file_type != 3:
            raise DFile.NonSymLink

    def get_link(self):
        link_bin = self.read_bin_array(0, self.size)
        link = self.bin_to_str(link_bin)
        return link