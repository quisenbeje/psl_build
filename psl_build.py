#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Evaluate and/or build fnl files for specified psl source files

This module contains functions which process a set of incoming source files to 
determine which fnl files these source files affect. With the appropriate options
selected the script will also search for all other (non-included) source files
which include the incoming source files.

The script produces a set of build trees which specify the necessary fnl files
in the appropriate order. This tree is returned and if not specified to only
display the tree then the script will proceed with building these fnl files in the
local directory, using psl commands.

"""

# import sys, getopt, os, re, tempfile, shutil
import sys, os, re, tempfile, shutil, time, glob
from optparse import OptionParser
from subprocess import Popen, PIPE, STDOUT
import tree

start_time = time.time()
################################################################################
# set global variables
################################################################################
exclude_dirs  = set(['SPARC_SOL','WRSGNUPPC604','MERCURY','GEN_TGT','.fnl_files','build_results'])
exclude_files = set(['~$','all_includes'])
local_source_files = []
build_files = []
handles = []
# psl_terms = set([])
# fnl_loc='./.fnl_files'
# bin_loc='./binaries'
# support = bin_loc + '/support_binaries'
cwd      = os.path.abspath(os.getcwd())
fnl_loc  = cwd + '/.fnl_files'
bin_loc  = cwd + '/build_results'
support  = bin_loc + '/support_binaries'
log_file = bin_loc + '/stdout.log'
# level prefixes used to format record output
levelPrefix = ['   ', '│  ', '├─ ', '╰─ ']
# psl terms, i.e. csci's, csc's, levels
# psl_terms = [
    # 'csci01',  'csci03',  'csci04',  'csci06',  'csci07',  'csci08',
    # 'csci10',  'csci12',  'csci13',  'csci15',  'csci16',  'csci17',  'site_lrr-1',
    # 'csc00',   'csc01',   'csc02',   'csc03',   'csc04',   'csc05',   'csc06',
    # 'csc07',   'csc08',   'csc09',   'csc10',   'csc11',   'csc12',   'csc13',
    # 'csc14',   'csc15',   'csc16',   'csc17',   'csc18',   'csc19',   'csc20',
    # 'csc22',   'csc23',   'csc25',   'csc27',   'csc28',
    # 'unt',     'prg',     'cpt',     'csi',     'int',     'fix',     'tst',
    # 'hsw',     'sys',     'ccb',     'frz',     'stt',     'del']
# source_file_rgx = ['(\S+\.c)', '(\S+\.cpp)', '(\S+\.h)', '(\S+\.hpp)']
source_file_rgx = ['(\S+\.[ch](pp)?)']
psl_term_rgx = [ 'csc(i)?\d{2}',  'site_lrr-1',
    'unt',     'prg',     'cpt',     'csi',     'int',     'fix',     'tst',
    'hsw',     'sys',     'ccb',     'frz',     'stt',     'del']

################################################################################
# class and function definitions
################################################################################
# Color options for the output to terminal
class color:

    """Define color sets and regex expressions which insert the colors

    This class requires no instance. All instances are static and all members are
    global to class

    """
    active    = False
    log_only  = False
    BOLD      = '\033[1m'          # bold
    UNDERLINE = '\033[4m'          # underline
    END       = '\033[0m'          # no color
    HANDLE    = '\033[1;38;5;82m'  # green bold
    LIB       = '\033[0;38;5;82m'  # green
    FNL       = '\033[0;38;5;82m'  # green
    SRC       = '\033[0;38;5;45m'  # blue
    SRC_B     = '\033[1;38;5;45m'  # blue bold
    CAP       = '\033[0;38;5;208m' # orange
    REFS      = '\033[1;38;5;244m' # grey
    PATH      = '\033[0;38;5;165m' # purple
    OTHER     = '\033[0;38;5;197m' # magenta
    WARN      = '\033[1;38;5;228m' # yellow bold
    ERROR     = '\033[1;38;5;124m' # red bold
    ERR       = '\033[0;38;5;124m' # red

    @staticmethod
    def addition(msg):
        """Add color to incoming string based on defined regex

        This is a static method and is to be called as follows:
        color.addition('any string')

        """
        # color rgx: line beginning with dash, hash, or at symbol
        rgx = r'(^\s*[-#@].*$)'
        if re.search(rgx, msg):
            msg = re.sub(rgx, color.REFS + r'\1' + color.END, msg)
        else:
            # color rgx: word LOCAL
            rgx = '(LOCAL)'
            msg = re.sub(rgx, color.CAP + r'\1' + color.END, msg)
            # color rgx: line starting with WARNING
            rgx = '(^WARNING.*$)'
            msg = re.sub(rgx, color.WARN + r'\1' + color.END, msg)
            # color rgx: line starting with ERROR
            rgx = '(.*)((?i)error)(.*$)'
            msg = re.sub(rgx, color.ERR + r'\1' + color.ERROR + r'\2' + 
                    color.ERR + r'\3' + color.END, msg)
            # color rgx: word following 'handle is:'
            rgx = '(handle is:\s)(.*$)'
            msg = re.sub(rgx, r'\1' + color.HANDLE + r'\2' + color.END, msg)
            # color rgx: word following BUILDING
            rgx = '(BUILDING\s+)(\w+)'
            msg = re.sub(rgx, r'\1' + color.HANDLE + r'\2' + color.END, msg)
            # color rgx: build source file
            for psl in psl_term_rgx:
            # for psl in psl_terms:
                # rgx = r'([^/])\b(%s)\b' % psl
                rgx = r'([^/])\b(%s)(?!:)\b' % psl
                msg = re.sub(rgx, r'\1' + color.OTHER + r'\2' + color.END, msg)
            # color rgx: local_source_files // slows as files increase
            for src in local_source_files:
                rgx = r'\b(%s)\b' % src
                msg = re.sub(rgx, color.SRC_B + r'\1' + color.END, msg)
            # # color rgx: build source file
            for rgx in source_file_rgx:
            # for src in local_source_files:
                # rgx = r'\b(%s)\b' % src
                msg = re.sub(rgx, color.SRC + r'\1' + color.END, msg)
            # # color rgx: build handles
            for hdl in handles:
                rgx = r'\b(%s([cC][0-9]+)?(?!\.))\b' % hdl
                # msg = re.sub(rgx, color.SRC_B + r'\1' + color.END, msg)
                msg = re.sub(rgx, color.HANDLE + r'\1' + color.END, msg)
            # color rgx: using local files not in handles or local source
            rgx = '(Using Local\s+)(\w+)'
            msg = re.sub(rgx, r'\1' + color.SRC + r'\2' + color.END, msg)
            # color rgx: other library files
            rgx = '([\s/])(\w+\.([ax]|lib))'
            msg = re.sub(rgx, r'\1' + color.LIB + r'\2' + color.END, msg)
            # color rgx: fnl files
            rgx = '([\s/])(\w+\.fnl)'
            msg = re.sub(rgx, r'\1' + color.FNL + r'\2' + color.END, msg)
            # color rgx: build location path
            rgx = '(\S+SPARC_SOL/?)'
            msg = re.sub(rgx, color.PATH + r'\1' + color.END, msg)
        return msg

def relative_to_cwd(pth):
    """Returns the incoming path as a relative path to the current working directory

    """
    if os.path.commonprefix([pth,os.getcwd()]) == os.getcwd():
        return '.' + pth[len(os.getcwd()):]
    else:
        return pth


def path_to_path_relative_to_base(crnt, dest, base):
    """Get a relative path to dest starting at crnt and going through the specified
    base directory.

    Both crnt and dest paths must have a base that includes the base path

    """

    class PathError(Exception):
        pass

    if (os.path.commonprefix([crnt,base]) == base and
        os.path.commonprefix([dest,base]) == base):
        # the directory and the base have the same root
        to_base = crnt[len(base):]
        to_base = re.sub('/\w+', '../', to_base)
        to_dest = to_base + dest[len(base)+1:]
        return to_dest
    else:
        raise PathError('one or more path does not contain the base directory: \ncrnt: %s\ndest: %s\nbase: %s\n' % (crnt, dest, base))


# all purpose print function. 
# handles coloring, inline, and stderr prints
def do_print(msg, **keywords):
    msg = str(msg)
    # msg = re.sub(os.getcwd(), '.', msg)
    msg = re.sub(cwd, '.', msg)
    bmsg = msg
    # include color
    if color.active and (sys.stdout.isatty() or 'stderr' in keywords):
        msg = color.addition(msg)

    # inline print will not automatically add a new line
    if ('inline' in keywords):
        # prints to stderr
        if ('stderr' in keywords):
            sys.stderr.write(msg)
            
        # prints to stdout
        else:
            sys.stdout.write(msg)
            sys.stdout.flush()

    # prints to stderr
    elif ('stderr' in keywords):
        # adds a new line if it isn't there
        if msg[-1] != '\n':
            msg = ('').join(msg, '\n')
            file.write('\n')
        sys.stderr.write(msg)

    # use default print function
    else:
        if not color.log_only:
            print msg
        file = open(log_file, 'a')
        file.write(bmsg.rstrip() + '\n')
        file.close()



# get parameter items from an fnl
# e.g. HANDLE item
def get_fnl_params(param, fnl):
    found_param = False
    f = open(fnl,'r')
    # read in file one line at a time
    for num, line in enumerate(f):
        if not found_param:
            if re.search(param, line):
                found_param = True
            continue
        else:
            # break loop if a line is found starting with '**'
            if re.search('^\*\*', line):
                break

            # search for line starting with a file
            m = re.search('^\s*(\w\S+)', line)
            # if a match is found return it
            if m: 
                # print 'found result ', m.group(1), num
                f.close()
                return m.group(1), num + 1

    f.close()




class progress:
    type = 'bar'

    class InvalidType(Exception):
        pass

    def __init__(self,verb=''):
        self.ndx     = 0
        self.size    = 0
        self.width   = 40
        self.verb    = verb
        self.info    = ''
        self.empty   = ' '
        self.front   = '['
        self.back    = ']'
        self.symbol  = '.'
        self.symbols = []
        if progress.type == 'bar':
            self.update = self.bar_update
        elif progress.type == 'symbols':
            self.update = self.symbols_update
        else:
            raise progress.InvalidType('invalid progress type selected')

    def increment(self, ndx=1, **kwargs):
        self.ndx += ndx
        if ('symbol' in kwargs):
            self.symbol = kwargs['symbol']
        self.update()

    def decrement(self, ndx=1, **kwargs):
        self.ndx -= ndx
        if ('symbol' in kwargs):
            self.symbol = kwargs['symbol']
        self.update()

    def grow(self, sz=1, **kwargs):
        self.size += sz
        if ('symbol' in kwargs):
            self.symbol = kwargs['symbol']
        self.update()

    def shrink(self, sz=1, **kwargs):
        self.size -= sz
        if ('symbol' in kwargs):
            self.symbol = kwargs['symbol']
        self.update()

    def add_info(self, msg):
        self.info = msg

    def bar_update(self):
        self.empty = '-'
        percent = float(self.ndx)/self.size
        if percent < 0:
            percent = 0
            text = "\nHalt...\n"
        else:
            cursor = "         \r"
            if percent >= 1:
                percent = 1
                cursor = "   \n"
            cursor = ('%s %d/%d %s%s' % (self.verb, self.ndx, self.size, self.info, cursor))
            block = int(round(self.width*percent))
            text = "# [%s] %s" % ("#"*block + self.empty*(self.width-block), cursor)
        do_print(text, inline=True, stderr=True)

    def symbols_update(self):
        self.empty = '_'

        # reset list if it is already the length of width
        if len(self.symbols) >= self.width:
            self.symbols = []
        self.symbols.append(self.symbol)
        syms = ("").join(x for x in self.symbols) + self.empty*(
                self.width - len(self.symbols))

        # if ndx equal to size
        if self.ndx >= self.size:
            # last print line
            cursor = self.verb + (' %d/%d' % (self.ndx, self.size)) + '   \n'
        # if symbol list is equal to width
        elif len(self.symbols) == self.width:
            # last print on this line. don't need ndx/size print
            cursor = ' '*(80-self.width) + '\n'
        # all other prints
        else:
            # this should get over written on next print
            cursor = self.verb + (' %d/%d' % (self.ndx, self.size)) + '   \r'

        text = "# [%s] %s" % (syms, cursor)
        do_print(text, inline=True, stderr=True)


def follow_files_tree(file_tree, location):
    new_files=[]

    fol_prog = progress('followed files')

    # create a copy of the file tree to hold follow results
    follow_tree = tree.tree()
    follow = follow_tree.add_node('follow')
    for x in file_tree.root.children:
        follow.add_node(x.id)
        new_files.append(x.id)

    # start processing with dictionary copy of flat library items
    fol_prog.size = follow.degree

    # tmp = tempfile.NamedTemporaryFile()
    fd, path = tempfile.mkstemp()

    while len(new_files):
        # clear contents of temp file
        tmp = open(path, 'wr+')
        tmp.write(('\n').join(new_files))
        tmp.close()
        num = len(new_files)
        new_files = []


        cmd = ['/usr/bin/fgrep', '-f', path, location]
        # cmd = ['/usr/bin/egrep', '-f', path, location]
        p = Popen(cmd, stdout=PIPE, bufsize=1)
        pat = r's/.*\/\(.*\):#include.*["<]\(.*\)[">]/\1:\2/'
        cmd2= ['/usr/bin/sed', pat]
        p2= Popen(cmd2, stdin=p.stdout,stdout=PIPE, bufsize=1)
        for result in iter(p2.stdout.readline, ''):
            # get file grep result
            r = result.rstrip().split(':')
            if len(r) == 2 and r[0] not in file_tree.nodes and r[1] in file_tree.nodes:
                # follow.add_node(bname)
                new_files.append(r[0])
                file_tree.get_node(r[1]).add_node(r[0])
                fol_prog.grow(symbol='+')
        fol_prog.increment(num, symbol='-')

    os.remove(path)

    do_print('', inline=True, stderr=True)

# def catalog_list(file_tree, location):
def catalog_list(file_tree, location, show_src=False):
    src_files = []
    new_files = []

    # create a copy of the file tree to hold follow results
    for x in file_tree.root.descendants:
        src_files.append(x.id)
    new_files = src_files[:]

    # create a copy of the file tree to hold follow results
    cat_tree = tree.tree()
    cat = cat_tree.add_node('catalog')

    # initialize progress display
    cat_prog = progress('resolved to fnl')
    cat_prog.size = len(file_tree.nodes) - 1

    # tmp = tempfile.NamedTemporaryFile()
    fd, path = tempfile.mkstemp()

    # create handles dictionary and function to coordinate handle id with filename
    handles = {}
    def get_handle_title(key):
        return '%s: %s' % (key, handles[key])

    while len(new_files):
        # clear contents of temp file
        tmp = open(path, 'wr+')
        tmp.write(('\n').join(new_files))
        tmp.close()

        # save new files for later use then clear out list
        old_files = new_files[:]
        new_files = []

        # create chain of subprocess filters
        # fgrep terms in tmp file over files in specified location
        cmd1 = ['/usr/bin/fgrep']
        cmd1.append('-nf')
        cmd1.append(path)
        cmd1.extend(glob.glob(location + '/*'))
        p1 = Popen(cmd1, stdout=PIPE, bufsize=1)
        # edit fgrep output to delete lines which don't match a specified 
        #    regex pattern
        cmd2 = ['/usr/bin/sed']
        cmd2.append(r'/.*\/.*:[0-9][0-9]*: *\([a-zA-Z][a-zA-Z0-9_-\.]*\) *$/!d')
        p2= Popen(cmd2, stdin=p1.stdout,stdout=PIPE, bufsize=1)
        # edit sed output to capture three main components using regex, 
        #    name of file term was found, linenum, and search term
        cmd3 = ['/usr/bin/sed']
        cmd3.append(r's/.*\/\(.*\):\([0-9][0-9]*\): *\([a-zA-Z][a-zA-Z0-9_-\.]*\).*$/\1:\2:\3/')
        p3= Popen(cmd3, stdin=p2.stdout,stdout=PIPE, bufsize=1)
        # process filter results
        for result in p3.communicate()[0].splitlines():
            # get file and line number from grep result
            f_name, num, s_name = result.split(':')[:3]
            if s_name not in old_files: 
                continue

            # get handle and handle line number
            hdl, h_num = get_fnl_params('HANDLE',location + '/' + f_name)
            if (int(num) > int(h_num)):
                handles[hdl] = f_name
                f_name = get_handle_title(hdl)

                try:
                    # get fnl node in tree
                    f_node = cat_tree.get_node(f_name)
                except:
                    # fnl is not in tree. add it
                    f_node = cat.add_node(f_name)
                    if hdl not in new_files:
                        new_files.append(hdl)
                        cat_prog.grow(symbol='+')
                        cat_prog.increment(symbol='+')

                try:
                    # get search-term node in tree
                    s_node = cat_tree.get_node(s_name)
                    # move search-term node to child of fnl node
                    if s_node.level == 1:
                        f_node.adopt_subtree(s_node)
                    else:
                        f_node.add_node(s_name)
                except:
                    # search-term node not in tree
                    try:
                        # get handle name in tree.
                        s_node = cat_tree.get_node(get_handle_title(s_name))
                        # move search-term node to child of fnl node
                        if s_node.level == 1:
                            f_node.adopt_subtree(s_node)
                        else:
                            f_node.add_node(s_name)
                    except:
                        # neither search term or handle name is in tree
                        # add search-term node as child of fnl node
                        if show_src:
                            f_node.add_node(s_name)
                        else:
                            if s_name not in src_files:
                                f_node.add_node(s_name)

        cat_prog.grow(len(new_files), symbol='+')
        cat_prog.shrink(len(old_files), symbol='-')

    os.remove(path)

    do_print('', inline=True, stderr=True)
    return cat_tree, handles



##### not used in the script: adds too much time #######
# get all psl terms, i.e. csci's, csc's, and level's
def get_psl_terms():
    p = Popen(['list','cscis'], stdout=PIPE)
    for ln in p.stdout:
        nodes = re.search(r'^\s*([a-z][a-z_0-9-]+)', ln)
        if nodes:
            psl_terms.add(nodes.group(1))
            os.environ["CSCI"] = nodes.group(1)
            pp = Popen(['list','cscs'], stdout=PIPE)
            for lnn in pp.stdout:
                nnodes = re.search(r'^\s*(csc[0-9]+)', lnn)
                if nnodes:
                    psl_terms.add(nnodes.group(1))
                    os.environ["CSC"] = nnodes.group(1)
                    ppp = Popen(['list','levels'], stdout=PIPE)
                    for lnnn in ppp.stdout:
                        nnnodes = re.search(r'^\s*(\w{3})\s', lnnn)
                        if nnnodes:
                            psl_terms.add(nnnodes.group(1))

def main():
    """Execute the psl_build script.

    """

    ################################################################################
    # set up script options
    ################################################################################
    usag='usage: ' + color.BOLD + '%prog' + color.END + (
            ''' [options] [source_files | source_directories]''')

    desc=color.BOLD + '%prog' + color.END + (
    ''':                                               
    creates build trees for all the source files specified by the files or   
    directories passed into the script, or, if nothing is passed in, the 
    files beneath the current working directory. finally, the psl 'build' 
    command is executed on each branch of the tree from bottom to top.''')

    parser = OptionParser(description=desc, usage=usag)
    parser.add_option(
        "-l", 
        "--list", 
        action="store_true", 
        dest="list", 
        default=False, 
        help="list source files and associated fnl files")

    parser.add_option(
        "-L", 
        "--log-only", 
        action="store_true", 
        dest="log_only", 
        default=False, 
        help="view output in log only")

    parser.add_option(
        "-c", 
        "--color",
        action="store_true",
        dest="color",
        default=False,
        help="colorize output")

    parser.add_option(
        "-v", 
        "--verbose",
        action="store_true",
        dest="verb",
        default=False,
        help="show more detailed output")

    parser.add_option(
        "-s", 
        "--show-source",
        action="store_true",
        dest="src",
        default=False,
        help="show source files. used with -v and -l options")

    parser.add_option(
        "-f", 
        "--follow",
        action="store_true",
        dest="follow",
        default=False,
        help="follow local files, i.e. add all files including locals")

    help_read ='''read local fnl files from "%s" rather than fetching files and
    writing them to a temporary directory''' % (fnl_loc) 

    parser.add_option(
        "-r", 
        "--read-fnls", 
        action="store_true", 
        dest="read", 
        default=False,
        help=help_read)

    parser.add_option(
        "-w", 
        "--write-fnls",
        action="store_true",
        dest="write",
        default=False,
        help='fetch all fnl files to the local directory "%s"' % (fnl_loc))

    help_catalog_symbols ='''show symbols detailing the catalog process.
          %s'-' - remove source file, not found in fnl files.
          %s'#' - cataloged source file found in fnl file.
          %s'+' - fnl handle added to catalog for processing.
          %s'@' - cataloged fnl handle found in another fnl file.
          %s'^' - fnl handle is at the top of its build tree.''' % (
                  ' '*4,' '*35,' '*15,' '*15,' '*15)
    parser.add_option(
        "-C", 
        "--catalog-symbol",
        action="store_true",
        dest="symbols",
        default=False,
        help=help_catalog_symbols)

    (options, args) = parser.parse_args()


    # define source progress bar
    if options.symbols:
        progress.type = 'symbols'

    if not os.path.isdir(bin_loc):
        # local binary directory doesn't exist
        cmd = ['mkdir', bin_loc]
        Popen(cmd).wait()
        if options.verb:
            do_print('\n# making local binary directory: "%s"' % (" ".join(cmd)))
        # make local binaries directory
    else:
        # local binary directory does exist from previous build
        cmd = ['rm', '-r']
        cmd.extend(glob.glob(bin_loc + '/*'))
        if options.verb:
            do_print('\n# clearing contents of local binary directory: "%s"' % (" ".join(cmd)))
        # remove previous links from local binary directory
        Popen(cmd).wait()

    
    if not os.path.isdir(support):
        # local support binary directory doesn't exist
        cmd = ['mkdir', support]
        if options.verb:
            do_print('\n# making local binary support directory: "%s"' % (" ".join(cmd)))
        # make local binaries support directory
        Popen(cmd).wait()
    ################################################################################
    # get all local source files
    ################################################################################
    # if no arguments are passed in use current directory
    if not args: args.append(os.getcwd())

    if options.color:
        color.active = True

    if options.log_only:
        color.log_only = True

    if options.verb:
        do_print('# collecting source files')
        included_files = 0
        total_files    = 0
        included_dirs  = 0
        total_dirs     = 0

    # simple version for working with CWD

    possible_files = 0
    for entry in args:
        if os.path.isfile(entry):
            possible_files += 1
        elif os.path.isdir(entry):
            for (dirpath, dirs, filenames) in os.walk(entry):
                possible_files += len(filenames)

    if not possible_files:
        print('no source files available to script\n')
        parser.print_help()
        sys.exit(1)


    src_prog = progress('files found')

    src_prog.size = possible_files

    # parse file or directory inputs
    for entry in args:
        # entry is a file
        if os.path.isfile(entry):
            # add files to set which do not match exclude_files
            for i in exclude_files:
                if not re.search(i, entry):
                    # add file
                    if options.verb:
                        if options.src: src_prog.add_info('++ %s\n' % entry)
                        included_files += 1
                        total_files    += 1
                    local_source_files.append(entry)
                    src_prog.increment(symbol='+')
                else:
                    # remove file from possible files
                    if options.verb:
                        if options.src: src_prog.add_info('-- %s\n' % entry)
                        total_files    += 1
                    src_prog.shrink(symbol='-')
        # entry is a directory
        elif os.path.isdir(entry):
            # walk recursively through the directory and get files
            for (dirpath, dirs, filenames) in os.walk(entry):
                if options.src and options.verb: do_print ('#    %s' % dirpath)
                # remove excluded dirs
                skip_dir = False
                for i in exclude_dirs:
                    if re.search(i, relative_to_cwd(dirpath)):
                        # remove all files in directory from possible files
                        skip_dir = True
                        if options.verb:
                            if options.src: src_prog.add_info('-- all files\n')
                            total_dirs += 1
                        src_prog.shrink(len(filenames),symbol='X')
                        break
                if skip_dir:
                    continue
                if options.verb:
                    included_dirs += 1
                    total_dirs    += 1

                # add filenames not matching the exclude set
                for filename in filenames:
                    exclude_file = False
                    for i in exclude_files:
                        if re.search(i, filename): exclude_file = True

                    if exclude_file:
                        # remove file from possible files
                        if options.verb:
                            if options.src: src_prog.add_info('-- %s\n' % filename)
                            total_files    += 1
                        src_prog.shrink(symbol='-')
                    else:
                        # add file
                        if options.verb:
                            if options.src: src_prog.add_info('++ %s\n' % filename)
                            included_files += 1
                            total_files    += 1
                        local_source_files.append(filename) 
                        src_prog.increment(symbol='+')

        # invalid entry
        else: 
            do_print('psl_build error: the local source file or directory does not exist')
            do_print('\t%s' % os.path.abspath(entry))
            sys.exit(1)

    if options.verb:
        do_print('# processing %d/%d files from %d/%d directories' 
                % (included_files, total_files, included_dirs, total_dirs))

    src_tree = tree.tree()
    top = src_tree.add_node('top')

    # add local source files to library
    for src in local_source_files:
        top.add_node(src)

    # determine what build files include the local source files
    # NOTE: currently the 'all_includes' files represents build 270
    if options.follow:
        follow_files_tree(src_tree, '/export/home/jquisenberry/builds/tst_cord/all_includes')

    if options.verb:
        if options.src: do_print(src_tree)


    ################################################################################
    # process script options and set working fnl directory
    ################################################################################
    # handle -w write option
    if options.write:
        if not os.path.isdir(fnl_loc):
            cmd = ['mkdir', fnl_loc]
            if options.verb:
                do_print('\n# making local directory: "%s"' % (" ".join(cmd)))
            Popen(cmd)
        fnl_dir = fnl_loc
        # read option is not necessary
        if options.read: options.read = False

    # handle -r read option
    if options.read:
        if options.verb:
            do_print('# accessing local fnl directory: %s' % os.path.abspath(fnl_loc))
        if not os.path.isdir(fnl_loc):
            do_print('psl_build error: the local fnl directory does not exist: %s' % os.path.abspath(fnl_loc))
            sys.exit(1)
        fnl_dir = fnl_loc

    # check to make sure the fnl_dir has been set
    try:
        fnl_dir
    except NameError:
        # make temporary directory for fnl files
        fnl_dir = tempfile.mkdtemp()
        if options.verb:
            do_print('# temporary fnl directory: %s' % os.path.abspath(fnl_dir))





    ################################################################################
    # fetch fnl files if they are not being read in from local directory
    ################################################################################
    if not options.read:
        if options.verb:
            do_print('\n# fetching fnl files into %s' % os.path.abspath(fnl_dir))

        # set psl env variables
        os.environ["CSCI"]  = 'site_lrr-1'
        os.environ["CSC"]   = 'csc00'
        os.environ["LEVEL"] = "int"

        # define fetch progress bar
        fetch_prog = progress('fetched fnls')


        # get fnl files and put them in temp dir
        pg = Popen(['progress'], stdout=PIPE).stdout.readlines()
        fetch_prog.size = len(pg)
        for ndx, lnnn in enumerate(pg):
            nodess = re.search(r'([a-zA-Z][a-zA-Z0-9_-]*\.fnl)', lnnn)
            if nodess:
                fetch_prog.increment(symbol='+')
                Popen(['fetch', str(nodess.group(1))], stderr=PIPE, cwd=fnl_dir)
            else:
                fetch_prog.shrink(symbol='-')


    if options.verb:
        do_print('\n# catalog source files by fnl files')

    # get tree and dictionary of fnl files affected by the files in the source tree
    # b_tree, b_dict = catalog_list(src_tree, fnl_dir)
    b_tree, b_dict = catalog_list(src_tree, fnl_dir, show_src=options.src)
    print b_dict
    handles = {}

    # loop through build subtrees
    for child in b_tree.root.children:
        if options.verb or options.list or options.log_only:
            # show local fnl build trees
            do_print('# %s, local build fnl tree:' % child.id.split(':')[0])
            do_print(child)
        if not options.list:
            # compile list of subtree nodes, leaves first
            nodes = child.descendants
            nodes.append(child)
            # loop through all nodes of build subtrees
            for dep in nodes:
                itm = dep.id.split(':')
                # handle = dep.id.split(':')[0]
                handle = itm[0]
                if len(itm) > 1:
                    handles[itm[1].lstrip()] = handle
                try:
                    build_files.append(b_dict.pop(handle))
                except KeyError:
                    pass


    if not options.list:

        # Source psl template and set environment variables
        cmd = ['bash', '-c',
            'source /psl/templates/psl.bash && psl site_lrr-1 csc00 int && env']
        proc = Popen(cmd, stdout=PIPE, bufsize=1)
        if options.verb:
            do_print('# source psl.bash and call psl to set environment variables')
            do_print('# \t$ %s' % (' ').join(cmd))
        # for line in proc.stdout:
        for line in iter(proc.stdout.readline, ''):
            rsl = line[:-1].split('=')
            if len(rsl) == 2 and (
                rsl[0] == 'CSCI' or
                rsl[0] == 'CSC' or
                rsl[0] == 'LEVEL' or
                rsl[0] == 'pdir' or
                rsl[0] == 'PSLPROJECT' or
                rsl[0] == 'PWD'):
                if options.verb:
                    do_print('# \t%s' % line[:-1])
                os.environ[rsl[0]] = rsl[1]

        ############################################################################
        # build all necessary fnl files
        ############################################################################
        # define fetch progress bar
        build_prog = progress('build files')
        build_prog.size = len(build_files)
        binaries = {}
        # loop through build files and build
        for x in build_files:
            do_print('\n\n# building fnl file: %s' % x)
            if options.verb:
                cmd = ['/psl/bin/SPARC_SOL/build', '-Lv', x]
            else:
                cmd = ['/psl/bin/SPARC_SOL/build', '-L', x]
            # cmd = ['build','-L', x]
            if options.verb:
                do_print('# $ %s' % (' ').join(cmd))
            p = Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1)
            # for result in Popen(cmd, stdout = PIPE).stdout:
            for lnn in iter(p.stdout.readline, ''):
                do_print(lnn[:-1])
                wds = lnn.split()
                # find output line starting with 'BUILDING'
                # if wds and wds[0] == 'USING' and wds[1] == 'FNL':
                    # fnl = wds[-1]
                if wds and wds[0] == 'BUILDING':
                    # use contents of line to find binary and directory
                    new_bin = wds[1]
                    new_loc = wds[-1]
                    # binaries[new_bin] = new_loc
                    # print wds, b_dict
                    # for key, val in handles.iteritems():
                        # print key, val, ':', x
                        # if val == x:
                    print x
                    print new_bin
                    root = re.sub('c[^c]+$','',new_bin)
                    print 'root:', root
                    print 'handle:', handles[x]
                    # suffix = handles[x].split(root)[1]
                    hdl = handles[x].split('.')
                    if len(hdl) > 1:
                        suffix = '.' + hdl[-1]
                    else:
                        suffix = ''
                    print 'suffix:', suffix
                    new_bin = new_bin + suffix
                    binaries[new_bin] = new_loc
                if wds and len(wds) == 2 and wds[0] == '-':
                    # use contents of line to find binary and directory
                    print wds
                    old_bin = wds[1].split('.log')[0] + suffix
                    print old_bin
                if len(wds) > 4  and (
                        (' ').join([wds[1],wds[2],wds[3],wds[4]]) == 'image up to date,'):
                    del binaries[new_bin]
                    binaries[old_bin] = new_loc
                    print new_bin, '=', old_bin

            # build_prog.add_info(': %s' % x)
            build_prog.increment(symbol='+')


        for key, val in binaries.iteritems():
            ref = re.sub(r'(\S+)c\d+', r'\1', key)
            is_main_bin = False
            for i in b_tree.root.children:
                if ref == i.id.split(':')[0]:
                    is_main_bin = True
                    break
            if is_main_bin:
                dst = bin_loc
            else:
                dst = support
            cmd2 = ['ln', '-s', path_to_path_relative_to_base(dst, val + '/' + key, cwd), '.'] 
            if options.verb:
                do_print('# link to binaries from %s: "%s"' % (dst, " ".join(cmd2)))
            # add soft links to binaries from local binary directory
            os.chdir(dst)
            Popen(cmd2).wait()
            os.chdir(cwd)

    ################################################################################
    # clean-up
    ################################################################################
    if os.path.dirname(fnl_dir) == '/tmp':
        if options.verb:
            do_print('\n# remove temp directory: %s' % fnl_dir)
        shutil.rmtree(fnl_dir)

    if options.verb:
        do_print ('# execution time: %s' % round(float(time.time() - start_time), 2))


if __name__ == '__main__':
    # this will only run when the module is run directly, i.e. not when it is
    # imported
    main()
