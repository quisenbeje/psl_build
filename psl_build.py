#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys, getopt, os, subprocess, re, tempfile, shutil
import time, pprint
from optparse import OptionParser

start_time = time.time()
################################################################################
# set global variables
################################################################################
exclude_dirs  = set(['SPARC_SOL','.fnl_files'])
exclude_files = set(['~$'])
local_source_files = []
library = {}
build_files = []
handles = []
# psl_terms = set([])
fnl_loc='./.fnl_files'
# level prefixes used to format record output
levelPrefix = ['   ', '│  ', '├─ ', '╰─ ']
# psl terms, i.e. csci's, csc's, levels
psl_terms = [
    'csci01',  'csci03',  'csci04',  'csci06',  'csci07',  'csci08',
    'csci10',  'csci12',  'csci13',  'csci15',  'csci16',  'csci17',  'site_lrr-1',
    'csc00',   'csc01',   'csc02',   'csc03',   'csc04',   'csc05',   'csc06',
    'csc07',   'csc08',   'csc09',   'csc10',   'csc11',   'csc12',   'csc13',
    'csc14',   'csc15',   'csc16',   'csc17',   'csc18',   'csc19',   'csc20',
    'csc22',   'csc23',   'csc25',   'csc27',   'csc28',
    'unt',     'prg',     'cpt',     'csi',     'int',     'fix',     'tst',
    'hsw',     'sys',     'ccb',     'frz',     'stt',     'del']
source_file_rgx = ['(\S+\.c)', '(\S+\.cpp)', '(\S+\.h)', '(\S+\.hpp)']
psl_term_rgx = [ 'csc(i)?\d{2}',  'site_lrr-1',
    'unt',     'prg',     'cpt',     'csi',     'int',     'fix',     'tst',
    'hsw',     'sys',     'ccb',     'frz',     'stt',     'del']

################################################################################
# class and function definitions
################################################################################
# Color options for the output to terminal
class color:
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
                rgx = r'([^/])\b(%s)\b' % psl
                msg = re.sub(rgx, r'\1' + color.OTHER + r'\2' + color.END, msg)
            # # color rgx: build source file
            for rgx in source_file_rgx:
            # for src in local_source_files:
                # rgx = r'\b(%s)\b' % src
                msg = re.sub(rgx, color.SRC_B + r'\1' + color.END, msg)
            # # color rgx: build handles
            for hdl in handles:
                rgx = r'\b(%s([cC][0-9]+)?)\b' % hdl
                # msg = re.sub(rgx, color.SRC_B + r'\1' + color.END, msg)
                msg = re.sub(rgx, color.HANDLE + r'\1' + color.END, msg)
            # color rgx: using local files not in handles or local source
            rgx = '(Using Local\s+)(\w+)'
            msg = re.sub(rgx, r'\1' + color.SRC + r'\2' + color.END, msg)
            # color rgx: other library files
            rgx = '([\s/])(\w+\.a)'
            msg = re.sub(rgx, r'\1' + color.LIB + r'\2' + color.END, msg)
            # color rgx: fnl files
            rgx = '([\s/])(\w+\.fnl)'
            msg = re.sub(rgx, r'\1' + color.FNL + r'\2' + color.END, msg)
            # color rgx: build location path
            rgx = '(\S+SPARC_SOL/?)'
            msg = re.sub(rgx, color.PATH + r'\1' + color.END, msg)
        return msg


class record:
    # initialize record
    def __init__(self, data):
        self.src = data
        # self.lvl = [levelPrefix[3]]
        self.lvl = [levelPrefix[0]]
        self.refs = []
        self.locked_in = False

    # move up a level, including refs
    def level_up(self, parent):
        if self.lvl[-1] == levelPrefix[0]:
            self.lvl[-1] = levelPrefix[3]
        # take on parent levels except last one
        self.lvl[:-1] = parent.lvl[:]
        # if the parent has an entry beneath it
        if self.lvl[-2] == levelPrefix[2]:
            # add extention at that level
            self.lvl[-2] = levelPrefix[1]
        else:
            # add gap at that level
            self.lvl[-2] = levelPrefix[0]
        for x in self.refs:
            x.level_up(self)

    # add reference record to self and level up ref
    def add_ref(self, nrecord):
        if len(self.refs) > 0:
            nrecord.lvl[-1] = levelPrefix[2]
        nrecord.level_up(self)
        self.refs.insert(0, nrecord)

    # put handle source (fnl file) into arg list
    def handle_source(self, out):
        if hasattr(self, 'handle'):
            out.insert(0, self.src)

    # get all handle sources (fnl files) and return in list
    def list_handle_source(self):
        out = []
        self.handle_source(out)
        for x in self.refs:
            x.handle_source(out)
        return out

    # put handles into arg list
    def handles(self, out):
        if hasattr(self, 'handle'):
            out.insert(0, self.handle)

    # get all handles and return in list
    def list_handles(self):
        out = []
        self.handles(out)
        for x in self.refs:
            x.handles(out)
        return out

    # format the printing of a record
    def __str__(self):
        lst = self.lvl[:]
        try: lst.append('%s: ' % self.handle)
        except AttributeError: pass
        lst.append('%s\n' % (self.src))
        [lst.append('%s' % x) for x in self.refs]
        return ('').join(x for x in lst)


# all purpose print function. 
# handles coloring, inline, and stderr prints
def do_print(msg, **keywords):
    msg = str(msg)
    msg = re.sub(os.getcwd(), '.', msg)
    if options.color and (sys.stdout.isatty() or 'stderr' in keywords):
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
        sys.stderr.write(msg)

    # use default print function
    else:
        print msg


# get parameter items from an fnl
# e.g. HANDLE item
def get_fnl_params(param, fnl):
    # put file lines into a list
    f = open(fnl,'r')
    lines = f.readlines()
    f.close()

    # get the list index matching param
    beg = [i for i, item in enumerate(lines) if re.search(param, item)]

    # return nothing if there are no matches
    if len(beg) < 1: return

    line_num = beg[0] + 1
    # loop through lines list starting at param line
    for wlk in lines[beg[0]+1:]:
        line_num += 1
        # break loop if a line is found starting with '**'
        if re.search('^\*\*', wlk): break

        # search for line starting with a file
        # assume every file has a '.' char
        m = re.search('^\s*(\w\S+)', wlk)
        # if a match is found return it
        if m: 
            return m.group(1), line_num


class progress:
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

class bar(progress):
    def update(self):
        self.empty = '-'
        percent = float(self.ndx)/self.size
        if percent < 0:
            percent = 0
            text = "\nHalt...\n"
        else:
            cursor = "   \r"
            if percent >= 1:
                percent = 1
                cursor = "   \n"
            if self.info == '':
                cursor = self.verb + (' %d/%d' % (self.ndx, self.size)) + cursor
            else:
                cursor = ('%s %d/%d %s\n' % (self.verb, self.ndx, self.size, self.info))
            block = int(round(self.width*percent))
            text = "# [%s] %s" % ("#"*block + self.empty*(self.width-block), cursor)
        do_print(text, inline=True, stderr=True)

class symbols(progress):
    def update(self):
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


# recursively grep a library of records at a given location
def catalog(lib, location):

    uncataloged = True
	
    if options.symbols:
        cat_prog = symbols('cataloged files')
    else:
        cat_prog = bar('cataloged files')

    cat_prog.size = len(lib)

    while uncataloged:
        # loop through source set
        for title, book in list(lib.iteritems()):

            # look at uncataloged books
            if not book.locked_in:
                # grep fnl files for input files (using regex)
                # loop through results
                try:
                    ptrn = '^' + book.handle + '[[:space:]]*$'
                except AttributeError:
                    ptrn = '^' + title + '[[:space:]]*$'
                cmd = ['/usr/sfw/bin/ggrep', '-rne', ptrn, location]
                found = False
                for result in subprocess.Popen(cmd, stdout = subprocess.PIPE).stdout:
                    # get file and line number from grep result
                    r_name, num = result.split(':')[:2]

                    # check to see if grep result is a valid file name
                    if os.path.isfile(r_name):
                        # get handle and handle line number
                        hdl, h_num = get_fnl_params('HANDLE',r_name)
                        # make sure the grep line number is greater than the handle 
                        # line number, i.e. we don't care about the HANDLE grep 
                        # result or anything above it
                        if (int(num) > int(h_num)):
                            found = True
                            # add fnl to library
                            bname = os.path.basename(r_name)
                            if bname not in lib:
                                cat_prog.grow(symbol='+')
                                lib[bname] = record(bname)
                            # remove book from library
                            del lib[title]
                            book.locked_in = True
                            if hasattr(book, 'handle'):
                                cat_prog.increment(symbol='@')
                            else:
                                cat_prog.increment(symbol='#')
                            # add book as ref to fnl
                            if options.src or hasattr(book, 'handle'):
                                lib[bname].add_ref(book)
                            lib[bname].handle = hdl
                            break

                # no result found during grep
                if not found:
                    if hasattr(book,'handle'):
                        book.locked_in = True
                        cat_prog.increment(symbol='^')
                    else:
                        # remove book from library
                        del lib[title]
                        # cat_prog.increment(symbol='-')
                        cat_prog.shrink(symbol='-')

        uncataloged = False

        # loop through source set
        for title, book in lib.iteritems():
            if not book.locked_in:
                uncataloged =+ 1
    do_print('', inline=True, stderr=True)


##### not used in the script: adds too much time #######
# get all psl terms, i.e. csci's, csc's, and level's
def get_psl_terms():
    p = subprocess.Popen(['list','cscis'], stdout=subprocess.PIPE)
    for ln in p.stdout:
        nodes = re.search(r'^\s*([a-z][a-z_0-9-]+)', ln)
        if nodes:
            psl_terms.add(nodes.group(1))
            os.environ["CSCI"] = nodes.group(1)
            pp = subprocess.Popen(['list','cscs'], stdout=subprocess.PIPE)
            for lnn in pp.stdout:
                nnodes = re.search(r'^\s*(csc[0-9]+)', lnn)
                if nnodes:
                    psl_terms.add(nnodes.group(1))
                    os.environ["CSC"] = nnodes.group(1)
                    ppp = subprocess.Popen(['list','levels'], 
                            stdout=subprocess.PIPE)
                    for lnnn in ppp.stdout:
                        nnnodes = re.search(r'^\s*(\w{3})\s', lnnn)
                        if nnnodes:
                            psl_terms.add(nnnodes.group(1))


################################################################################
# set up script options
################################################################################
usag='usage: ' + color.BOLD + '%prog' + color.END + (
        ''' [options] [source_files | source_directories]''')

desc=color.BOLD + '%prog' + color.END + ''' - creates build trees for all
the source files specified by the files or directories passed into the script,
or, if nothing is passed in, the files beneath the current working directory.
finally, the psl 'build' command is executed on each branch of the tree from 
bottom to top.'''

parser = OptionParser(description=desc, usage=usag)
parser.add_option(
    "-l", 
    "--list", 
    action="store_true", 
    dest="list", 
    default=False, 
    help="list source files and associated fnl files")

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

################################################################################
# get all local source files
################################################################################
# if no arguments are passed in use current directory
if not args: args.append(os.getcwd())

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


# define source progress bar
if options.symbols:
    src_prog = symbols('files found')
else:
    src_prog = bar('files found')

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
                    if options.src: src_prog.add_info('++ %s' % entry)
                    included_files += 1
                    total_files    += 1
                src_prog.increment(symbol='+')
                local_source_files.append(entry)
            else:
                # remove file from possible files
                if options.verb:
                    if options.src: src_prog.add_info('-- %s' % entry)
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
                if re.search(i, os.path.basename(dirpath)):
                    # remove all files in directory from possible files
                    skip_dir = True
                    if options.verb:
                        if options.src: src_prog.add_info('-- all files')
                        total_dirs += 1
                    src_prog.shrink(len(filenames),symbol='X')
                    break
            if skip_dir:
                continue
            if options.verb:
                included_dirs += 1
                total_dirs    += 1

            # add filenames not matching the exclude set
            for i in exclude_files:
                for filename in filenames:
                    if not re.search(i, filename):
                        # add file
                        if options.verb:
                            if options.src: src_prog.add_info('++ %s' % filename)
                            included_files += 1
                            total_files    += 1
                        src_prog.increment(symbol='+')
                        local_source_files.append(filename) 
                    else:
                        # remove file from possible files
                        if options.verb:
                            if options.src: src_prog.add_info('-- %s' % filename)
                            total_files    += 1
                        src_prog.shrink(symbol='-')
    # invalid entry
    else: 
        do_print('psl_build error: the local source file or directory does not exist')
        do_print('\t%s' % os.path.abspath(entry))
        sys.exit(1)

if options.verb:
    do_print('# processing %d/%d files from %d/%d directories' 
            % (included_files, total_files, included_dirs, total_dirs))
# add local source files to library
for src in local_source_files:
    library[src] = record(src)

################################################################################
# process script options and set working fnl directory
################################################################################
# handle -w write option
if options.write:
    if not os.path.isdir(fnl_loc):
        cmd = ['mkdir', fnl_loc]
        if options.verb:
            do_print('\n# making local directory: "%s"' % (" ".join(cmd)))
        subprocess.Popen(cmd)
    fnl_dir = fnl_loc
    # read option is not necessary
    if options.read: options.read = False

# handle -r read option
if options.read:
    if options.verb:
        do_print('# accessing local fnl directory: %s' % os.path.abspath(fnl_loc))
    if not os.path.isdir(fnl_loc):
        do_print('psl_build error: the local fnl directory does not exist')
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

    # pp = subprocess.Popen(['list','cscs'], stdout=subprocess.PIPE)
    # for lnn in pp.stdout:
        # nnodes = re.search(r'^\s*(csc[0-9]+)', lnn)
        # if nnodes:
            # os.environ["CSC"] = nnodes.group(1)

    # define fetch progress bar
    if options.symbols:
        fetch_prog = symbols('fetched files')
    else:
        fetch_prog = bar('fetched files')

    # get fnl files and put them in temp dir
    pg = subprocess.Popen(['progress'], stdout=subprocess.PIPE).stdout.readlines()
    fetch_prog.size = len(pg)
    for ndx, lnnn in enumerate(pg):
        nodess = re.search(r'([a-zA-Z][a-zA-Z0-9_-]*\.fnl)', lnnn)
        if nodess:
            fetch_prog.increment(symbol='+')
            subprocess.Popen(
                ['fetch', str(nodess.group(1))],
                stderr=subprocess.PIPE,
                cwd=fnl_dir)
        else:
            fetch_prog.shrink(symbol='-')


if options.verb:
    do_print('\n# catalog source files by fnl files')

catalog (library, fnl_dir)

for key, val in library.iteritems():
    build_files.extend(val.list_handle_source())
    handles.extend(val.list_handles())
    if options.verb or options.list:
        do_print('#  local build fnl tree:')
        do_print(val)

if not options.list:

    # Source psl template and set environment variables
    cmd = ['bash', '-c',
        'source /psl/templates/psl.bash && psl site_lrr-1 csc00 int && env']
    proc = subprocess.Popen(cmd, stdout = subprocess.PIPE)
    if options.verb:
        do_print('# source psl.bash and call psl to set environment variables')
        do_print('# \t$ %s' % (' ').join(cmd))
    for line in proc.stdout:
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
        for lnn in subprocess.Popen(
                cmd, 
                stdout = subprocess.PIPE,
                stderr= subprocess.STDOUT).stdout:
            # format build output
            do_print(lnn[:-1])

################################################################################
# clean-up
################################################################################
if os.path.dirname(fnl_dir) == '/tmp':
    if options.verb:
        do_print('\n# remove temp directory: %s' % fnl_dir)
    shutil.rmtree(fnl_dir)

if options.verb:
    do_print ('# execution time: %s' % round(float(time.time() - start_time), 2))
