import re
import os
import string
import logging

from annograph.exceptions import DelimiterError

NUMBER_CHARACTERS = set(string.digits)

class Attribute(object):
    """
    Attributes are for collecting summary information about attributes of
    Words or WordTokens, with different types of attributes allowing for
    different behaviour

    Parameters
    ----------
    name : str
        Python-safe name for using `getattr` and `setattr` on Words and
        WordTokens

    att_type : str
        Either 'spelling', 'tier', 'numeric' or 'factor'

    display_name : str
        Human-readable name of the Attribute, defaults to None

    default_value : object
        Default value for initializing the attribute

    Attributes
    ----------
    name : string
        Python-readable name for the Attribute on Word and WordToken objects

    display_name : string
        Human-readable name for the Attribute

    default_value : object
        Default value for the Attribute.  The type of `default_value` is
        dependent on the attribute type.  Numeric Attributes have a float
        default value.  Factor and Spelling Attributes have a string
        default value.  Tier Attributes have a Transcription default value.

    range : object
        Range of the Attribute, type depends on the attribute type.  Numeric
        Attributes have a tuple of floats for the range for the minimum
        and maximum.  The range for Factor Attributes is a set of all
        factor levels.  The range for Tier Attributes is the set of segments
        in that tier across the corpus.  The range for Spelling Attributes
        is None.
    """
    ATT_TYPES = ['spelling', 'tier', 'numeric', 'factor']
    def __init__(self, name, att_type, display_name = None, default_value = None):
        self.name = name
        self.att_type = att_type
        self._display_name = display_name

        if self.att_type == 'numeric':
            self._range = [0,0]
            if default_value is not None and isinstance(default_value,(int,float)):
                self._default_value = default_value
            else:
                self._default_value = 0
        elif self.att_type == 'factor':
            if default_value is not None and isinstance(default_value,str):
                self._default_value = default_value
            else:
                self._default_value = ''
            if default_value:
                self._range = set([default_value])
            else:
                self._range = set()
        elif self.att_type == 'spelling':
            self._range = None
            if default_value is not None and isinstance(default_value,str):
                self._default_value = default_value
            else:
                self._default_value = ''
        elif self.att_type == 'tier':
            self._range = set()
            self._delim = None
            if default_value is not None:
                self._default_value = default_value
            else:
                self._default_value = []

    @property
    def delimiter(self):
        if self.att_type != 'tier':
            return None
        else:
            return self._delim

    @delimiter.setter
    def delimiter(self, value):
        self._delim = value

    @staticmethod
    def guess_type(values, trans_delimiters = None):
        if trans_delimiters is None:
            trans_delimiters = ['.',' ', ';', ',']
        probable_values = {x: 0 for x in Attribute.ATT_TYPES}
        for i,v in enumerate(values):
            try:
                t = float(v)
                probable_values['numeric'] += 1
                continue
            except ValueError:
                for d in trans_delimiters:
                    if d in v:
                        probable_values['tier'] += 1
                        break
                else:
                    if v in [v2 for j,v2 in enumerate(values) if i != j]:
                        probable_values['factor'] += 1
                    else:
                        probable_values['spelling'] += 1
        return max(probable_values.items(), key=operator.itemgetter(1))[0]

    @staticmethod
    def sanitize_name(name):
        """
        Sanitize a display name into a Python-readable attribute name

        Parameters
        ----------
        name : string
            Display name to sanitize

        Returns
        -------
        string
            Sanitized name
        """
        return re.sub('\W','',name.lower())

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.display_name

    def __eq__(self,other):
        if isinstance(other,Attribute):
            if self.name == other.name:
                return True
        if isinstance(other,str):
            if self.name == other:
                return True
        return False

    @property
    def display_name(self):
        if self._display_name is not None:
            return self._display_name
        return self.name.title()

    @property
    def default_value(self):
        return self._default_value

    @default_value.setter
    def default_value(self, value):
        self._default_value = value
        self._range = set([value])

    @property
    def range(self):
        return self._range

    def update_range(self,value):
        """
        Update the range of the Attribute with the value specified.
        If the attribute is a Factor, the value is added to the set of levels.
        If the attribute is Numeric, the value expands the minimum and
        maximum values, if applicable.  If the attribute is a Tier, the
        value (a segment) is added to the set of segments allowed. If
        the attribute is Spelling, nothing is done.

        Parameters
        ----------
        value : object
            Value to update range with, the type depends on the attribute
            type
        """
        if value is None:
            return
        if self.att_type == 'numeric':
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    self.att_type = 'spelling'
                    self._range = None
                    return
            if value < self._range[0]:
                self._range[0] = value
            elif value > self._range[1]:
                self._range[1] = value
        elif self.att_type == 'factor':
            self._range.add(value)
            #if len(self._range) > 1000:
            #    self.att_type = 'spelling'
            #    self._range = None
        elif self.att_type == 'tier':
            if isinstance(self._range, list):
                self._range = set(self._range)
            self._range.update([x for x in value])


class BaseAnnotation(object):
    def __init__(self, label, begin = None, end = None):
        self.label = label
        self.begin = begin
        self.end = end
        self.stress = None
        self.tone = None
        self.group = None

    def __iter__(self):
        return iter(self.label)

    def __repr__(self):
        return '<BaseAnnotation "{}" from {} to {}>'.format(self.label,
                                                            self.begin,
                                                            self.end)
    def __eq__(self, other):
        if isinstance(other, BaseAnnotation):
            return self.label == other.label and self.begin == other.begin \
                    and self.end == other.end
        elif isinstance(other, str):
            return self.label == other
        return False

class Annotation(BaseAnnotation):
    def __init__(self, label, **kwargs):
        self.label = label
        self.begins = []
        self.ends = []
        self.references = []
        for k,v in kwargs.items():
            if isinstance(v, tuple):
                self.references.append(k)
                self.begins.append(v[0])
                self.ends.append(v[1])
            else:
                setattr(self, k, v)
        self.token = {}
        self.additional = {}

    def __eq__(self, other):
        return self.label == other.label and self.begins == other.begins \
                and self.ends == other.ends

    def __getitem__(self, key):
        for i, r in enumerate(self.references):
            if r == key:
                return self.begins[i], self.ends[i]
        return None

    def __repr__(self):
        return '<Annotation "{}">'.format(self.label)

class AnnotationType(object):
    def __init__(self, name, subtype, supertype, attribute = None, anchor = False,
                    token = False, base = False, speaker = None):
        self.characters = set()
        self.ignored_characters = set()
        self.digraphs = set()
        self.trans_delimiter = None
        self.morph_delimiters = set()
        self.number_behavior = None
        self._list = []
        self.name = name
        self.subtype = subtype
        self.supertype = supertype
        self.token = token
        self.base = base
        self.anchor = anchor
        self.speaker = speaker
        self.ignored = False
        if self.speaker is not None:
            self.output_name = re.sub('{}\W*'.format(self.speaker),'',self.name)
        else:
            self.output_name = self.name
        if attribute is None:
            if base:
                self.attribute = Attribute(Attribute.sanitize_name(name), 'tier', name)
            else:
                self.attribute = Attribute(Attribute.sanitize_name(name), 'spelling', name)
        else:
            self.attribute = attribute

    def pretty_print(self):
        string = ('{}:\n'.format(self.name) +
                '    Ignored characters: {}\n'.format(', '.join(self.ignored_characters)) +
                '    Digraphs: {}\n'.format(', '.join(self.digraphs)) +
                '    Transcription delimiter: {}\n'.format(self.trans_delimiter) +
                '    Morpheme delimiters: {}\n'.format(', '.join(self.morph_delimiters)) +
                '    Number behavior: {}\n'.format(self.number_behavior))
        return string

    def reset(self):
        self._list = []

    def __repr__(self):
        return '<AnnotationType "{}" with Attribute "{}"'.format(self.name,
                                                        self.attribute.name)

    def __str__(self):
        return self.name

    def __getitem__(self, key):
        return self._list[key]

    def add(self, annotations, save = True):
        for a in annotations:
            self.characters.update(a)
            if save or len(self._list) < 10:
                #If save is False, only the first 10 annotations are saved
                self._list.append(a)

    @property
    def delimited(self):
        if self.delimiter is not None:
            return True
        if self.digraphs:
            return True
        return False

    def __iter__(self):
        for x in self._list:
            yield x

    def __len__(self):
        return len(self._list)

    @property
    def digraph_pattern(self):
        if len(self.digraphs) == 0:
            return None
        return compile_digraphs(self.digraphs)

    @property
    def punctuation(self):
        return self.characters & set(string.punctuation)

    @property
    def delimiter(self):
        return self.trans_delimiter

    @delimiter.setter
    def delimiter(self, value):
        self.trans_delimiter = value

    @property
    def is_word_anchor(self):
        return not self.token and self.anchor

    @property
    def is_token_base(self):
        return self.token and self.base

    @property
    def is_type_base(self):
        return not self.token and self.base

class DiscourseData(object):
    def __init__(self, name, levels):
        self.name = name
        self.data = {x.name: x for x in levels}
        self.wav_path = None

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, item):
        return item in self.data

    @property
    def types(self):
        return self.keys()

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def items(self):
        return self.data.items()

    def mapping(self):
        return { x.name: x.attribute for x in self.data.values() if not x.ignored}

    def collapse_speakers(self):
        newdata = {}
        shifts = {self.data[x].output_name: 0 for x in self.base_levels}
        #Sort keys by speaker, then non-base levels, then base levels

        keys = list()
        speakers = sorted(set(x.speaker for x in self.data.values() if x.speaker is not None))
        for s in speakers:
            base = []
            for k,v in self.data.items():
                if v.speaker != s:
                    continue
                if v.base:
                    base.append(k)
                else:
                    keys.append(k)
            keys.extend(base)
        for k in keys:
            v = self.data[k]
            name = v.output_name
            if name not in newdata:
                subtype = v.subtype
                supertype = v.supertype
                if subtype is not None:
                    subtype = self.data[subtype].output_name
                if supertype is not None:
                    supertype = self.data[supertype].output_name
                newdata[v.output_name] = AnnotationType(v.output_name, subtype, supertype,
                    anchor = v.anchor,token = v.token, base = v.base,
                    delimited = v.delimited)
            for ann in v:
                newann = dict()
                for k2,v2 in ann.items():
                    try:
                        newk2 = self.data[k2].output_name
                        newv2 = (v2[0]+shifts[newk2],v2[1]+shifts[newk2])

                    except KeyError:
                        newk2 = k2
                        newv2 = v2
                    newann[newk2] = newv2

                newdata[v.output_name].add([newann])
            if v.base:
                shifts[v.output_name] += len(v)
        self.data = newdata

    @property
    def process_order(self):
        order = self.word_levels
        while len(order) < len(self.data.keys()) - len(self.base_levels):
            for k,v in self.data.items():
                if k in order:
                    continue
                if v.base:
                    continue
                if v.supertype is None:
                    order.append(k)
                    continue
                if v.supertype in order:
                    order.append(k)
        return order

    @property
    def word_levels(self):
        levels = []
        for k in self.data.keys():
            if self.data[k].is_word_anchor:
                levels.append(k)
        return levels

    @property
    def base_levels(self):
        levels = []
        for k in self.data.keys():
            if self.data[k].base:
                levels.append(k)
        return levels

    def add_annotations(self,**kwargs):
        for k,v in kwargs.items():
            self.data[k].add(v)

    def level_length(self, key):
        return len(self.data[key])

def get_corpora_list(storage_directory):
    corpus_dir = os.path.join(storage_directory,'CORPUS')
    corpora = [x.split('.')[0] for x in os.listdir(corpus_dir)]
    return corpora

def corpus_name_to_path(storage_directory,name):
    return os.path.join(storage_directory,'CORPUS',name+'.corpus')

def compile_digraphs(digraph_list):
    digraph_list = sorted(digraph_list, key = lambda x: len(x), reverse=True)
    pattern = '|'.join(re.escape(d) for d in digraph_list)
    pattern += '|\d+|\S'
    return re.compile(pattern)

def inspect_directory(directory):
    types = ['textgrid', 'text', 'multiple']
    counter = {x: 0 for x in types}
    relevant_files = {x: [] for x in types}
    for root, subdirs, files in os.walk(directory):
        for f in files:
            ext = os.path.splitext(f)[-1].lower()
            if ext == '.textgrid':
                t = 'textgrid'
            elif ext == '.txt':
                t = 'text'
            elif ext in ['.words','.wrds']:
                t = 'multiple'
            else:
                continue
            counter[t] += 1
            relevant_files[t].append(f)
    max_value = max(counter.values())
    for t in ['textgrid', 'multiple', 'text']:
        if counter[t] == max_value:
            likely_type = t
            break

    return likely_type, relevant_files

parse_numbers = re.compile('\d+|\S')

def parse_transcription(string, annotation_type):
    md = annotation_type.morph_delimiters
    if len(md) and any(x in string for x in md):
        morphs = re.split("|".join(md),string)
        transcription = []
        for i, m in enumerate(morphs):
            trans = parse_transcription(m, annotation_type)
            for t in trans:
                t.group = i
            transcription += trans
        return transcription
    ignored = annotation_type.ignored_characters
    if ignored is not None:
        string = ''.join(x for x in string if x not in ignored)
    if annotation_type.trans_delimiter is not None:
        string = string.split(annotation_type.trans_delimiter)
    elif annotation_type.digraph_pattern is not None:
        string = annotation_type.digraph_pattern.findall(string)
    else:
        string = parse_numbers.findall(string)
    final_string = []
    for seg in string:
        if seg == '':
            continue
        num = None
        if annotation_type.number_behavior is not None:
            if annotation_type.number_behavior == 'stress':
                num = ''.join(x for x in seg if x in NUMBER_CHARACTERS)
                seg = ''.join(x for x in seg if x not in NUMBER_CHARACTERS)
            elif annotation_type.number_behavior == 'tone':
                num = ''.join(x for x in seg if x in NUMBER_CHARACTERS)
                seg = ''.join(x for x in seg if x not in NUMBER_CHARACTERS)
            if num == '':
                num = None
            if seg == '':
                setattr(final_string[-1],annotation_type.number_behavior, num)
                continue
        a = BaseAnnotation(seg)
        if annotation_type.number_behavior is not None and num is not None:
            setattr(a, annotation_type.number_behavior, num)
        final_string.append(a)
    return final_string

def text_to_lines(path):
    delimiter = None
    with open(path, encoding='utf-8-sig', mode='r') as f:
        text = f.read()
        if delimiter is not None and delimiter not in text:
            e = DelimiterError('The delimiter specified does not create multiple words. Please specify another delimiter.')
            raise(e)
    lines = [x.strip().split(delimiter) for x in text.splitlines() if x.strip() != '']
    return lines

def find_wav_path(path):
    name, ext = os.path.splitext(path)
    wav_path = name + '.wav'
    if os.path.exists(wav_path):
        return wav_path
    return None

def log_annotation_types(annotation_types):
    logging.info('Annotation type info')
    logging.info('--------------------')
    logging.info('')
    for a in annotation_types:
        logging.info(a.pretty_print())

def data_to_discourse(data, lexicon = None):
    attribute_mapping = data.mapping()
    d = Discourse(name = data.name, wav_path = data.wav_path)
    ind = 0
    if lexicon is None:
        lexicon = d.lexicon

    for k,v in attribute_mapping.items():
        a = data[k]

        if a.token and v not in d.attributes:
            d.add_attribute(v, initialize_defaults = True)

        if not a.token and v not in d.lexicon.attributes:
            lexicon.add_attribute(v, initialize_defaults = True)

    for level in data.word_levels:
        for i, s in enumerate(data[level]):
            word_kwargs = {'spelling':(attribute_mapping[level], s.label)}
            word_token_kwargs = {}
            if s.token is not None:
                for token_key, token_value in s.token.items():
                    att = attribute_mapping[token_key]
                    word_token_kwargs[att.name] = (att, token_value)
            if s.additional is not None:
                for add_key, add_value in s.additional.items():
                    att = attribute_mapping[add_key]
                    if data[add_key].token:
                        word_token_kwargs[att.name] = (att, add_value)
                    else:
                        word_kwargs[att.name] = (att, add_value)
            for j, r in enumerate(s.references):
                if r in data and len(data[r]) > 0:
                    seq = data[r][s.begins[j]:s.ends[j]]
                    att = attribute_mapping[r]
                    if data[r].token:
                        word_token_kwargs[att.name] = (att, seq)
                        if len(seq) > 0 and seq[0].begin is not None:
                            word_token_kwargs['begin'] = seq[0].begin
                            word_token_kwargs['end'] = seq[-1].end

                    else:
                        word_kwargs[att.name] = (att, seq)

            word = lexicon.get_or_create_word(**word_kwargs)
            word_token_kwargs['word'] = word
            if 'begin' not in word_token_kwargs:
                word_token_kwargs['begin'] = ind
                word_token_kwargs['end'] = ind + 1
            wordtoken = WordToken(**word_token_kwargs)
            word.frequency += 1
            word.wordtokens.append(wordtoken)
            d.add_word(wordtoken)
            ind += 1
    return d
