# coding=utf-8

import re
import json
import gzip
import bz2
import argparse
import logging
from collections import OrderedDict

import tokenizers


logging.basicConfig(level=logging.INFO, datefmt='%m/%d %H:%M:%S',
                    format='[%(asctime)s] %(levelname)s: %(message)s')

regex_spaces = re.compile(r'\s+')
regex_hyperlink = re.compile(r'\[\[([^:]+?)\]\]')
regex_entity_token = re.compile(r'__\d+__')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cirrus_file', type=str,
                        help='Wikipedia Cirrussearch dump file (.json.gz)')
    parser.add_argument('out_file', type=str,
                        help='output corpus file (.txt.bz2)')
    # --tokenizer char optionを追加
    parser.add_argument('--tokenizer', choices=('regexp', 'nltk', 'mecab', 'char'),
                        default='regexp',
                        help='type of tokenizer [regexp]')
    parser.add_argument('--lower', action='store_true',
                        help='lowercase words (not applied to NEs)')
    parser.add_argument('--mecab_dic', type=str, default=None,
                        help='dictionary for MeCab tokenizer')
    parser.add_argument('--mecab_udic', type=str, default=None,
                        help='user dictionary for MeCab tokenizer')
    args = parser.parse_args()

    if args.tokenizer == 'regexp':
        logging.info('tokenizer: RegExpTokenizer')
        tokenizer = tokenizers.RegExpTokenizer(lower=args.lower)
    elif args.tokenizer == 'nltk':
        logging.info('tokenizer: NLTKTokenizer')
        tokenizer = tokenizers.NLTKTokenizer(lower=args.lower)
    elif args.tokenizer in ['mecab', 'char']:
        logging.info('tokenizer: MeCabTokenizer')
        logging.info(f'dictionary: {args.mecab_dic}')
        logging.info(f'user dictionary: {args.mecab_udic}')
        tokenizer = tokenizers.MeCabTokenizer(
            dic=args.mecab_dic, udic=args.mecab_udic, lower=args.lower)
    else:
        raise Exception('Undefined tokenizer type.')

    logging.info('generating corpus for training')
    n_processed = 0
    with gzip.open(args.cirrus_file, 'rt') as fi, \
            bz2.open(args.out_file, 'wt') as fo:
        for line in fi:
            article = json.loads(line)
            if 'title' not in article:
                continue

            title = article['title']
            text = regex_spaces.sub(r' ', article['text'])

            hyperlinks = dict()
            hyperlinks[title] = title
            for match in regex_hyperlink.finditer(article['source_text']):
                if '|' in match.group(1):
                    (entity, anchor) = match.group(1).split('|', maxsplit=1)
                else:
                    entity = anchor = match.group(1)

                if '#' in entity:
                    entity = entity[:entity.find('#')]

                anchor = anchor.strip()
                entity = entity.strip()
                if len(anchor) > 0 and len(entity) > 0:
                    hyperlinks.setdefault(anchor, entity)

            hyperlinks_sorted = OrderedDict(sorted(
                hyperlinks.items(), key=lambda t: len(t[0]), reverse=True))

            for (idx, hyperlink) in enumerate(hyperlinks_sorted.items()):
                (anchor, _) = hyperlink
                entity_token = f' __{idx}__ '
                text = text.replace(anchor, entity_token)

            text = ' '.join(tokenizer.tokenize(
                text, preserving_pattern=regex_entity_token))

            for (idx, hyperlink) in enumerate(hyperlinks_sorted.items()):
                (anchor, entity) = hyperlink
                # 通常の単語との区別をされないように変更
                entity = anchor if '(' in entity else entity
                idx_token = f'__{idx}__'
                # マークアップを施さないように変更
                hyperlink_token = f'{entity}'.replace(' ', '')
                hyperlink_token = ' '.join(tokenizer.tokenize(
                    hyperlink_token, preserving_pattern=regex_entity_token))
                text = text.replace(idx_token, hyperlink_token)

            # additional shaping
            #   - 注釈の"^"を削除
            #   - 文字単位での文の分割
            text = re.sub(r'\s\^', '', text)
            if args.tokenizer == 'char':
                tmp = filter(lambda a: a != ' ', list(text))
                text = ' '.join(tmp)

            print(text, file=fo)
            n_processed += 1
            if n_processed % 10000 == 0:
                logging.info(f'processed: {n_processed}')

    if n_processed % 10000 != 0:
        logging.info(f'processed: {n_processed}')


if __name__ == '__main__':
    main()
