#!/usr/bin/python
# -*- coding: utf-8 -*-
import weakref, gc, pprint

class tree(object):


    def __init__(self):
        self.nodes = {}
        self.orphans = {}

    @property
    def root(self):
        # return the root node of tree, if in one
        try: 
            nd = weakref.proxy(self.nodes.itervalues().next())
            if nd.is_root:
                return nd
            else:
                return nd.root
        except StopIteration:
            return None

    # add a node to tree. adds as child of root if parent is not 
    # specified. a weak reference to the new node is returned
    # def add_node(self, *args, **kwargs):
    # add node to orphanage unless parent is specified
    def add_node(self, id, **kwargs):
        # don't add a node with the same id as one that already exists in tree
        while id in self.nodes:
            id = id + '.'
        # if id in self.nodes:
            # id = id + '@'
            # print id
            # raise Exception('node id already in tree')
            # return
        nd = _node(id, self)
        if 'parent' in kwargs:
            p_node = self.get_node(kwargs['parent'])
            p_node.adopt(nd)
        if not self.nodes:
            self.nodes[nd.id] = self.orphans.pop(nd.__repr__(), None)

        return nd

    def add_root_node(self, id):
        if self.root:
            old_root = self.root
            nd = self.add_node(id)
            self.root.parent = nd
            self.nodes[nd.id] = self.orphans.pop(nd.__repr__(), None)
            nd.children.append(old_root)
        else:
            nd = self.add_node(id)
        return nd


    # insert a node into the tree. insert differs from add_node in 
    # that an inserted node will have no siblings. if 'before' or 
    # 'after' reference node is not specified the node is inserted 
    # as parent of root. a weak reference to the new node is returned
    def insert_node(self, id, **kwargs):
        if 'before' in kwargs:
            p_node = self.get_node(kwargs['before'])
            if p_node.is_root:
                self.add_root_node(id)
            else:
                nd = self.add_node(id)
                p_node.parent.adopt(nd)
                nd.adopt_subtree(p_node)
        elif 'after' in kwargs:
            p_node = self.get_node(kwargs['after'])
            kids = p_node.children[:]
            nd = self.add_node(id)
            p_node.adopt(nd)
            for x in kids:
                nd.adopt_subtree(x)
        else:
            return self.add_root_node(id)
        return nd



    # delete a node, or nodes, in the tree. node must be a leaf, i.e. has no children
    def delete_node(self, *args):
        for id in args:
            self.get_node(id).delete()

    # delete a subtree, i.e. the node and all descendants
    def delete_subtree(self, *args):
        for id in args:
            lst = self.get_node(id).list_subtree_ids()
            for sub_id in lst:
                print sub_id
                self.delete_node(sub_id)

    def get_descendants(self, *args):
        rtn = {}
        for id in args:
            rtn.update(self.get_node(id).get_descendants())
        return rtn


    # def adopt_node(self, child_id, new_parent_id):
        # child = self.get_node(child_id)
        # child.set_parent(self.get_node(new_parent_id))

    # get node via id
    def get_node(self, id):
        # !!! what if parent doesn't exist?
        if id in self.nodes:
            return weakref.proxy(self.nodes[id])
        elif id in self.orphans:
            return weakref.proxy(self.orphans[id])
        else:
            raise Exception('node (%s) not in tree.nodes or tree.orphans' % id)

    def get_node_ref(self, id):
        return weakref.proxy(self.get_node(id))

    def __str__(self):
        return self.root.__str__()

    def __repr__(self):
        return self.nodes.__repr__()



# private class
# object in a tree data structure. a node can have a parent and children nodes.
class _node(object):
    mark_prefix = ['╰─ ', '├─ ']
    lead_prefix = ['   ', '│  ']
    _ref = {} # dict contains reference btw weakref of node and tree of node
              # this allows for tree operations to be executed by the node

    # creates an instance of _node and add it to incoming dictionary
    # as root or child of root. returns a weak proxy to instance
    def __new__(obj, id, tree):
    # def __new__(obj, id, nds):
        # if id in tree.nodes:
            # raise Exception('node id already in tree')
            # return
        self = super(_node, obj).__new__(obj)
        try:
            _node.index += 1
        except AttributeError:
            _node.index = 0


        self.id       = id
        self.index    = _node.index
        self.children = []   # list of child nodes
        self.parent   = 0    # make root temporarily
        nd = weakref.proxy(self)
        # try:
            # # add new node as child of root
            # tree.nodes.itervalues().next().root.add_child(nd)

            # # tree.nodes.itervalues().next().root.add_child(weakref.proxy(self))
            # # nds.itervalues().next().root.add_child(weakref.proxy(self))
        # except StopIteration:
            # # no values in nds, i.e. there is no existing root. keep node as root
            # pass
        # tree.nodes[id] = self
        tree.orphans[id] = self
        # !!! this gets over written if two trees have the same node name !!!
        # _node._ref[nd.__repr__()] = weakref.proxy(tree)
        _node._ref[self.index] = weakref.proxy(tree)
        # nds[id] = self
        return nd
        # return weakref.proxy(self)

    # return string representation of self and descendants
    def __str__(self):
        rtn = [('%s\n' % (self.id))]
        rtn.extend(self.print_descendants())
        return ('').join(rtn)

    # return string representation of self
    def __repr__(self):
        return str(self.id)

    # proof of garbage collection
    # def __del__(self):
        # print '%s died' % (self.id)

    @property
    def tree(self):
        # return _node._ref[self.__repr__()]
        return _node._ref[self.index]

    @property
    def degree(self):
        return len(self.children)

    @property
    def is_leaf(self):
        if self.height:
            return False
        else:
            return True

    @property
    def is_root(self):
        if self.parent or self.is_orphan:
            return False
        else:
            return True

    @property
    def is_orphan(self):
        if self.__repr__() in self.tree.orphans:
            return True
        else:
            return False

    @property
    def level(self):
        # return the number of nodes to root
        lvl = 0
        root = self
        while root.parent:
            root = root.parent
            lvl += 1
        return lvl

    @property
    def height(self):
        # return the number of nodes to root
        hgt = 0
        for child in self.children:
            c_hgt = child.height + 1
            if c_hgt > hgt: hgt = c_hgt
        return hgt

    @property
    def root(self):
        # return the root node of tree
        node = self
        if self.is_orphan:
            raise Exception('node is an orphan')
        while not node.is_root:
            node = node.parent
        return node

    @property
    def path_to_root(self):
        # return list of nodes between self and root, inclusively
        lst = [self]
        if not self.is_root:
            lst.extend(self.parent.path_to_root)
        return lst

    @property
    def ancestors(self):
        # return list of ancestor nodes
        lst = []
        if not self.is_root:
            lst.extend(self.parent.path_to_root)
        return lst

    @property
    def siblings(self):
        # return list of ancestor nodes
        lst = []
        if not self.is_root:
            lst.extend(self.parent.children)
            lst.remove(weakref.proxy(self))
        return lst

    @property
    def descendants(self):
        # return list of descendant nodes
        lst = []
        for x in self.children:
            lst.extend(x.descendants)
            lst.append(x)
        return lst

    @property
    def info(self):
        rtn = []
        rtn.append(' id.........%s' % self.id)
        rtn.append(' level......%s' % self.level)
        rtn.append(' height.....%s' % self.height)
        rtn.append(' is leaf....%s' % self.is_leaf)
        rtn.append(' is root....%s' % self.is_root)
        rtn.append(' is orphan..%s' % self.is_orphan)
        rtn.append(' degree.....%s' % self.degree)
        if self.parent:
            rtn.append(' parent.....%s' % self.parent.id)
        else:
            rtn.append(' parent.....None')
        rtn.append(' siblings...%d<%s>' % 
                (len(self.siblings), ','.join(x.id for x in self.siblings)))
        rtn.append(' children...%d<%s>' % 
                (len(self.children), ','.join(x.id for x in self.children)))
        print ('\n'.join(rtn))


    def add_node(self, id):
        return self.tree.add_node(id, parent=self.id)

    def insert_node(self, id, after=False):
        if after:
            return self.tree.insert_node(id, after=self.id)
        else:
            return self.tree.insert_node(id, before=self.id)


    # add child node to self and level up child and descendants
    def add_child(self, child):
        # print 'add', child.id, 'to parent', self.id
        # print self
        # print child
        if child in self.path_to_root:
            print 'child', child.id, 'ancestor of self', self.id
            # child.remove_child(self)

        # print type(child)
        if child.parent:
            # print 'child to add has family ... first orphan child', child.id
            child.disown(child.parent)


        # for r in weakref.getweakrefs(child):
            # print 'xxx weakref found child', child.id, hex(id(child.id)), hex(id(r))
        self.children.append(child) # add new child to list of children
        # if child.parent:
            # child.parent.remove_child(child)
        child.parent = self


    def adopt(self, child):
        if not child.is_orphan:
            raise Exception('can only adopt orphan nodes')

        # if child.parent:
            # # print child.id, 'disowns parent,', self.id
            # child.disown(child.parent)
        # print 'child\n', child.info
        # print 'parent\n', self.info
        self.add_child(child)
        self.tree.nodes[child.id] = self.tree.orphans.pop(child.__repr__(), None)

    def adopt_subtree(self, child):
        if self.__repr__() not in self.tree.nodes and child.__repr__() not in self.tree.nodes:
            raise Exception('subtree must be in same tree as node')
        # if subtree root already has a parent. remove subtree root from its
        # old parent's child list
        if child.parent:
            child.parent.children.remove(child)
        # set subtree parent to self
        child.parent = self
        # add subtree root to self's children list
        self.children.append(child)




    def disown(self, relation):
        # clean up child's old relationships
        if relation == self.parent:
            # print 'child disowns parent'
            son    = self
        elif relation in self.children:
            # print 'parent disowns child'
            son    = relation
        else:
            return

        son.orphan()

    def orphan(self):
        if self not in self.tree.nodes:
            raise Exception('node is already an orphan')
        self.tree.orphans[self.id] = self.tree.nodes.pop(self.__repr__(), None)
        if self.parent:
            self.parent.remove_child(self)
            self.parent = 0

    # remove child node if it exists
    # children are assigned as weak references; so the reference
    # itself has to be found and removed
    def remove_child(self, kid):
        # get all weakrefs to kid
        # print 'from', self.id, 'delete kid', kid.id
        for r in weakref.getweakrefs(kid):
            # if weakref to kid in children
            if r in self.children:
                self.children.remove(r)
                kid.parent = 0
                # print ' delete weakref to', kid.id
            # else:
                # print ' no weakref to', kid.id



    # remove self and dependants from any tree
    # def break_away(self):
        # self.set_parent(0)

    # remove node and it's dependants from any tree
    # def trim(self, disown):
        # disown.break_away()

    ###### i don't like this name - i don't know why it's needed ######
    # return a dictionary of nodes from node and descendants
    def list_children(self):
        rtn = {}
        rtn[self.id] = self
        for x in self.children:
            rtn.update(x.list_children())
        return rtn

    def get_descendants(self):
        rtn = {}
        for x in self.children:
            rtn[x.id] = x
            rtn.update(x.list_children())
        return rtn

    # return subree id's children first
    def list_subtree_ids(self):
        rtn = []
        for x in self.children:
            rtn.extend(x.list_subtree_ids())
        rtn.append(self.id)
        return rtn

    # return a list of descendants with leaders and markers
    def print_descendants(self, prefix=[]):
        rtn = []
        # called from outside of recursion
        if not prefix:
            _node.local_level = self.level

        # print '@@@', self.degree, self.id
        for x in self.children:
            leader = ['']

            level_diff = x.level - _node.local_level
            prefix = prefix[:(level_diff-1)]

            for y in prefix:
                leader.append(_node.lead_prefix[y])

            if x.parent.children.index(x) == (len(x.parent.children)-1):
                prefix.append(0)
                leader.append(_node.mark_prefix[0])
            else:
                prefix.append(1)
                leader.append(_node.mark_prefix[1])

            rtn.append('%s%s\n' % (('').join(leader),  x.id))

            # recursive call. pass in current prefix list
            rtn.extend(x.print_descendants(prefix=prefix))

        return rtn


    # delete self
    def delete(self):
        if not self.is_leaf:
            raise Exception('cannot delete a node with children')

        # remove all references to node to allow for garbage collection
        if self.parent:
            # print 'delete child of', self.parent.id
            self.parent.remove_child(self)
        self.children = []
        # remove hard reference to node, in tree.nodes, to allow for 
        # garbage collection
        self.tree.nodes.pop(self.__repr__(), None)
        # remove weak reference to node in _node._ref dict
        # _node._ref.pop(self.__repr__(), None)
        _node._ref.pop(self.index, None)


    # delete descendants nodes and self
    def delete_subtree(self):
        for x in self.descendants:
            x.delete()
        self.delete()


# s = tree()
# a = s.add_node('a')
# b = a.add_node('b')
# c = a.add_node('c')
# d = c.add_node('d')
# e = c.add_node('e')
# x = a.add_node('x')
# print s
# d.add_node('x')

# t = tree()
# ta = t.add_node('a')
# print t
# print 'add z to node a of tree s'
# z = a.add_node('z')
# print s
# print t



# i = s.insert_node('i',after='a')
# print s

# z = s.insert_node('z',before='c')
# print s



# t=tree()
# t.add_node('a')
# t.add_node('b', parent='a')
# t.add_node('c', parent='a')
# t.add_node('d', parent='b')
# t.add_node('e', parent='b')
# t.add_node('f', parent='b')
# t.add_node('i', parent='e')
# t.add_node('j', parent='e')
# t.add_node('g', parent='c')
# t.add_node('h', parent='c')
# t.add_node('k', parent='g')
# print t

# nd = t.get_node('e')
# t.add_node('new')
# new = t.get_node('new')
# print 'setting parent with weakrefs'
# new.add_child(nd)
# # new.adopt(nd)
# print t

# for r in weakref.getweakrefs(t.nodes['e']):
    # print r
