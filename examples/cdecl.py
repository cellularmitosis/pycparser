#-----------------------------------------------------------------
# pycparser: cdecl.py
#
# Example of the CDECL tool using pycparser. CDECL "explains" C type
# declarations in plain English.
#
# The AST generated by pycparser from the given declaration is traversed
# recursively to build the explanation. Note that the declaration must be a
# valid external declaration in C. As shown below, typedef can be optionally
# expanded.
#
# For example:
#
#   c_decl = 'typedef int Node; const Node* (*ar)[10];'
#
#   explain_c_declaration(c_decl)
#   => ar is a pointer to array[10] of pointer to const Node
#
# struct and typedef can be optionally expanded:
#
#   explain_c_declaration(c_decl, expand_typedef=True)
#   => ar is a pointer to array[10] of pointer to const int
#
#   c_decl = 'struct P {int x; int y;} p;'
#
#   explain_c_declaration(c_decl)
#   => p is a struct P
#
#   explain_c_declaration(c_decl, expand_struct=True)
#   => p is a struct P containing {x is a int, y is a int}
#
# Eli Bendersky [https://eli.thegreenplace.net/]
# License: BSD
#-----------------------------------------------------------------
import copy
import sys

# This is not required if you've installed pycparser into
# your site-packages/ with setup.py
sys.path.extend(['.', '..'])

from pycparser import c_parser, c_ast


def explain_c_declaration(c_decl, expand_struct=False, expand_typedef=False):
    """ Parses the declaration in c_decl and returns a text
        explanation as a string.

        The last external node of the string is used, to allow earlier typedefs
        for used types.

        expand_struct=True will spell out struct definitions recursively.
        expand_typedef=True will expand typedef'd types.
    """
    parser = c_parser.CParser()

    try:
        node = parser.parse(c_decl, filename='<stdin>')
    except c_parser.ParseError:
        e = sys.exc_info()[1]
        return "Parse error:" + str(e)

    if (not isinstance(node, c_ast.FileAST) or
        not isinstance(node.ext[-1], c_ast.Decl)
        ):
        return "Not a valid declaration"

    try:
        expanded = expand_struct_typedef(node.ext[-1], node,
                                         expand_struct=expand_struct,
                                         expand_typedef=expand_typedef)
    except Exception as e:
        return "Not a valid declaration: " + str(e)

    return _explain_decl_node(expanded)


def _explain_decl_node(decl_node):
    """ Receives a c_ast.Decl note and returns its explanation in
        English.
    """
    storage = ' '.join(decl_node.storage) + ' ' if decl_node.storage else ''

    return (decl_node.name +
            " is a " +
            storage +
            _explain_type(decl_node.type))


def _explain_type(decl):
    """ Recursively explains a type decl node
    """
    typ = type(decl)

    if typ == c_ast.TypeDecl:
        quals = ' '.join(decl.quals) + ' ' if decl.quals else ''
        return quals + _explain_type(decl.type)
    elif typ == c_ast.Typename or typ == c_ast.Decl:
        return _explain_type(decl.type)
    elif typ == c_ast.IdentifierType:
        return ' '.join(decl.names)
    elif typ == c_ast.PtrDecl:
        quals = ' '.join(decl.quals) + ' ' if decl.quals else ''
        return quals + 'pointer to ' + _explain_type(decl.type)
    elif typ == c_ast.ArrayDecl:
        arr = 'array'
        if decl.dim: arr += '[%s]' % decl.dim.value

        return arr + " of " + _explain_type(decl.type)

    elif typ == c_ast.FuncDecl:
        if decl.args:
            params = [_explain_type(param) for param in decl.args.params]
            args = ', '.join(params)
        else:
            args = ''

        return ('function(%s) returning ' % (args) +
                _explain_type(decl.type))

    elif typ == c_ast.Struct:
        decls = [_explain_decl_node(mem_decl) for mem_decl in decl.decls]
        members = ', '.join(decls)

        return ('struct%s ' % (' ' + decl.name if decl.name else '') +
                ('containing {%s}' % members if members else ''))


def expand_struct_typedef(cdecl, file_ast,
                          expand_struct=False,
                          expand_typedef=False):
    """Expand struct & typedef and return a new expanded node."""
    decl_copy = copy.deepcopy(cdecl)
    _expand_in_place(decl_copy, file_ast, expand_struct, expand_typedef)
    return decl_copy


def _expand_in_place(decl, file_ast, expand_struct=False, expand_typedef=False):
    """Recursively expand struct & typedef in place, throw RuntimeError if
       undeclared struct or typedef are used
    """
    typ = type(decl)

    if typ in (c_ast.Decl, c_ast.TypeDecl, c_ast.PtrDecl, c_ast.ArrayDecl):
        decl.type = _expand_in_place(decl.type, file_ast, expand_struct,
                                     expand_typedef)

    elif typ == c_ast.Struct:
        if not decl.decls:
            struct = _find_struct(decl.name, file_ast)
            if not struct:
                raise RuntimeError('using undeclared struct %s' % decl.name)
            decl.decls = struct.decls

        for i, mem_decl in enumerate(decl.decls):
            decl.decls[i] = _expand_in_place(mem_decl, file_ast, expand_struct,
                                             expand_typedef)
        if not expand_struct:
            decl.decls = []

    elif (typ == c_ast.IdentifierType and
          decl.names[0] not in ('int', 'char')):
        typedef = _find_typedef(decl.names[0], file_ast)
        if not typedef:
            raise RuntimeError('using undeclared type %s' % decl.names[0])

        if expand_typedef:
            return typedef.type

    return decl


def _find_struct(name, file_ast):
    """Receives a struct name and return declared struct object in file_ast
    """
    for node in file_ast.ext:
        if (type(node) == c_ast.Decl and
           type(node.type) == c_ast.Struct and
           node.type.name == name):
            return node.type


def _find_typedef(name, file_ast):
    """Receives a type name and return typedef object in file_ast
    """
    for node in file_ast.ext:
        if type(node) == c_ast.Typedef and node.name == name:
            return node


if __name__ == "__main__":
    if len(sys.argv) > 1:
        c_decl  = sys.argv[1]
    else:
        c_decl = "char *(*(**foo[][8])())[];"

    print("Explaining the declaration: " + c_decl + "\n")
    print(explain_c_declaration(c_decl) + "\n")
