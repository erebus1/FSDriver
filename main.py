import Driver
from File import SimpleFile, Directory

__author__ = 'user'


def help():
    print("mount name\n"
          "unmount\n"
          "filestat descriptor_is\n"
          "ls\n"
          "open filepath\n"
          "create filepath\n"
          "close fd\n"
          "read fd\n"
          "write fd\n"
          "link exist_file_path new_file_path\n"
          "unlink filepath\n"
          "truncate filepath\n"
          "mkdir filepath\n"
          "rmdir filepath\n"
          "cd [filepath]\n"
          "pwd\n"
          "symlink content file_path_to_save\n"
          "exit\n")


def user_interface():
    """
    all staff information in help()
    """
    print "type 'help' if you need help"
    global driver
    driver = Driver.Driver()
    while True:
        command = raw_input(">>> ")
        command = " ".join(command.split())  # remove duplicated spaces
        command = command.strip()  # remove first and end spaces
        command = command.split(" ")
        if command[0] == "exit":
            break
        elif command[0] == "help":
            help()
        elif command[0] == "createFS":
            if len(command) > 1:
                driver.create_new_FS(command[1])
            else:
                print " no enough args"

        elif command[0] == "mount":
            if len(command) > 1:
                driver.mount(command[1])
            else:
                print " no enough args"
        elif command[0] == "unmount":
            driver.unmount()
        elif command[0] == "filestat":
            if len(command) > 1:
                try:
                    id = int(command[1])
                except ValueError:
                    print "wrong id parameter"
                    continue
                driver.file_stat(id)
            else:
                print " no enough args"
        elif command[0] == "ls":
            driver.ls()

        elif command[0] == "create":
            if len(command) > 1:
                driver.create(command[1])
            else:
                print " no enough args"

        elif command[0] == "open":
            if len(command) > 1:
                driver.open(command[1])
            else:
                print " no enough args"
        elif command[0] == "close":
            if len(command) > 1:
                try:
                    fd = int(command[1])
                except ValueError:
                    print "wrong fd parameter"
                    continue
                driver.close(fd)
            else:
                print " no enough args"
        elif command[0] == "read":
            if len(command) > 3:
                try:
                    fd = int(command[1])
                    shift = int(command[2])
                    size = int(command[3])
                except ValueError:
                    print "wrong fd parameter"
                    continue

                driver.read(fd, shift, size)
            else:
                print " no enough args"
        elif command[0] == "write":
            if len(command) > 3:
                try:
                    fd = int(command[1])
                    shift = int(command[2])
                except ValueError:
                    print "wrong fd parameter"
                    continue

                driver.write(fd, shift, command[3])
            else:
                print " no enough args"

        elif command[0] == "link":
            if len(command) >= 3:
                driver.link(command[1], command[2])
            else:
                print " no enough args"

        elif command[0] == "unlink":
            if len(command) > 1:
                driver.unlink(command[1])
            else:
                print " no enough args"
        elif command[0] == "truncate":
            if len(command) > 2:
                try:
                    size = int(command[2])
                except ValueError:
                    print "wrong fd parameter"
                    continue
                driver.truncate(command[1], size)
            else:
                print " no enough args"

        elif command[0] == "mkdir":
            if len(command) > 1:
                driver.mkdir(command[1])
            else:
                print " no enough args"
        elif command[0] == "rmdir":
            if len(command) > 1:
                driver.rmdir(command[1])
            else:
                print " no enough args"
        elif command[0] == "cd":
            if len(command) > 1:
                driver.cd(command[1])
            else:
                driver.cd()
        elif command[0] == "pwd":
            driver.pwd()
        elif command[0] == "symlink":
            if len(command) > 2:
                driver.symlink(command[1], command[2])
            else:
                print " no enough args"
        else:
            print "no such command\ntry call help"


def main():
    user_interface()


main()
