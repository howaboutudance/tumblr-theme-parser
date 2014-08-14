import re

from pyparsing import alphanums, Optional, Word, Literal
from pyparsing import SkipTo, makeHTMLTags, oneOf
from pyparsing import Forward, ParseException


def matchingCloseTag(openTag, closeTag):
    ret = Forward()
    ret << closeTag.copy()
    
    def setupMatchingClose(tokens):
        opentag = tokens[1]
        
        def mustMatch(tokens):
            if tokens[1] != opentag:
                raise ParseException("", 0, "")
        
        ret.setParseAction(mustMatch)
        
    openTag.addParseAction(setupMatchingClose)
    return ret


class Parser(object):
    """A Tumblr theme parser."""

    def __init__(self):
        self.template = ""
        self.rendered = ""
        self.options = {}

    def parse_theme(self, options, template):
        """Parse a template string with a dict of options."""
        self.options = options
        self.template = template
        self.rendered = template

        self._extract_meta_options()
        self.rendered = self._parse_template(self.options, self.template)

        return self.rendered

    def _extract_meta_options(self):
        """Fill options dictionary with metatags of template."""
        meta_start, meta_end = makeHTMLTags("meta")
        for token, start, end in meta_start.scanString(self.template):
            if ":" in token.name:
                value = token.content
                if token.name.startswith('if:'):
                    value = bool(int(value))
                    key = token.name.replace('if:', '')
                    key = ''.join(word.capitalize() for word in re.split(r'\s+', key))
                self.options[token.name] = value

    def _parse_template(self, options, template):
        """Parse a template string."""
        variable_name = Word(alphanums + " " + "-" + "_")
        variable_prefix = Optional(Literal('select:'))
        variable = "{" + variable_prefix + variable_name + "}"
        variable.setParseAction(self._replace_variable(options))

        block_type_name = oneOf("Text Photo Panorama Photoset Quote Link Chat Video Audio")
        block_type_start = "{block:" + block_type_name + "}"
        block_type_end = "{/block:" + block_type_name + "}"
        block_type = block_type_start + SkipTo(matchingCloseTag(block_type_start, block_type_end).leaveWhitespace(), include=True)
        block_type.setParseAction(self._replace_block_type(options))

        block_cond_name = Word(alphanums + "-" + "_")
        block_cond_start = "{block:If" + Optional("Not") + block_cond_name + "}"
        block_cond_end = "{/block:If" + Optional("Not") + block_cond_name + "}"
        block_cond = block_cond_start + SkipTo(matchingCloseTag(block_cond_start, block_cond_end).leaveWhitespace(), include=True)
        block_cond.setParseAction(self._replace_block_cond(options))

        block_def_cond_name = Word(alphanums + "-" + "_")
        block_def_cond_start = "{block:" + block_def_cond_name + "}"
        block_def_cond_end = "{/block:" + block_def_cond_name + "}"
        block_def_cond = block_def_cond_start + SkipTo(matchingCloseTag(block_def_cond_start, block_def_cond_end).leaveWhitespace(), include=True)
        block_def_cond.setParseAction(self._replace_block_def_cond(options))

        block_iter_name = oneOf("Posts Tags")
        block_iter_start = "{block:" + block_iter_name + "}"
        block_iter_end = "{/block:" + block_iter_name + "}"
        block_iter = block_iter_start + SkipTo(matchingCloseTag(block_iter_start, block_iter_end).leaveWhitespace(), include=True)
        block_iter.setParseAction(self._replace_block_iter(options))

        parser = (block_iter | block_type | block_cond | block_def_cond | variable)
        return parser.transformString(template)

    def _replace_variable(self, options):
        """Replace variables."""
        def conversionParseAction(string, location, tokens):
            var = "".join(tokens[1:-1])
            if var in options:
                return options[var]
            else:
                return ""
        return conversionParseAction

    def _replace_block(self, options):
        """Replace blocks."""
        def conversionParseAction(string, location, tokens):
            block_name = tokens[1]
            block_content = tokens[3]
            if block_name in options:
                return self._parse_template(options, block_content)
            else:
                return ""
        return conversionParseAction

    def _replace_block_type(self, options):
        """Replace by type of post."""
        def conversionParseAction(string, location, tokens):
            block_name = tokens[1]
            block_content = tokens[3][0]
            
            if block_name == options.get('PostType'):
                return self._parse_template(options, block_content)
            else:
                return ""
        return conversionParseAction

    def _replace_block_cond(self, options):
        """Replace a conditional block."""
        def conversionParseAction(string, location, tokens):
            num_tokens = len(tokens)
            if num_tokens == 5:
                block_name = tokens[2]
                block_content = tokens[4][0]
                block_bool = False
            if num_tokens == 4:
                block_name = tokens[1]
                block_content = tokens[3][0]
                block_bool = True

            if block_name in options and block_bool == options[block_name]:
                return self._parse_template(options, block_content)
            if block_bool == False:
                return self._parse_template(options, block_content)
            return ""
        return conversionParseAction

    def _replace_block_def_cond(self, options):
        """Replace a conditional block (checks if specified variable is defined)."""
        def conversionParseAction(string, location, tokens):
            block_name = tokens[1]
            block_content = tokens[3][0]
            
            if options.get(block_name, False):
                return self._parse_template(options, block_content)
            else:
                return ""
        return conversionParseAction

    def _replace_block_iter(self, options):
        """Replace blocks with content from an iterable."""
        def conversionParseAction(string, location, tokens):
            block_name = tokens[1]
            block_content = tokens[3][0]
            
            if block_name in options:
                rendered = ""
                for item_options in options[block_name]:
                    _options = options.copy()
                    _options.update(item_options)
                    
                    if block_name in _options:
                        del _options[block_name]
                    rendered += self._parse_template(_options, block_content)
                return rendered
        return conversionParseAction
