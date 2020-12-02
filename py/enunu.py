#! /usr/bin/env python3
# coding: utf-8
# Copyright (c) 2020 oatsu
"""
1. UTAUプラグインのテキストファイルを読み取る。
  - 音源のフォルダを特定する。
  - プロジェクトもしくはUSTファイルのパスを特定する。
2. LABファイルを(一時的に)生成する
  - キャッシュフォルダでいいと思う。
3. LABファイル→WAVファイル
"""

from datetime import datetime
from os import chdir, getcwd, makedirs
from os.path import relpath, splitdrive, splitext
from sys import argv

import utaupy as up
from hts2json import hts2json
from hts2wav import hts2wav
from hydra.experimental import compose, initialize
from ust2hts import convert_ustobj_to_htsfulllabelobj


def get_project_path(utauplugin: up.utauplugin.UtauPlugin):
    """
    キャッシュパスとプロジェクトパスを取得する。
    """
    # ustのパス
    path_ust = utauplugin.setting['Project']
    # 音源フォルダ
    voice_dir = utauplugin.setting['VoiceDir']
    # 音声キャッシュのフォルダ(LABとJSONを設置する)
    cache_dir = utauplugin.setting['CacheDir']

    return path_ust, voice_dir, cache_dir


def utauplugin2hts(path_plugin, path_hts, path_table, check=True, strict_sinsy_style=False):
    """
    USTじゃなくてUTAUプラグイン用に最適化する。
    ust2hts.py 中の ust2hts を改変して、
    [#PREV] と [#NEXT] に対応させている。
    """
    # 変換テーブルを読み取る
    table = up.table.load(path_table, encoding='utf-8')

    # プラグイン用一時ファイルを読み取る
    plugin = up.utauplugin.load(path_plugin)
    print('len(plugin.notes)', len(plugin.notes))
    # [#PREV] のノートを追加する
    if plugin.previous_note is None:
        prev_note_exits = False
    else:
        plugin.notes.insert(0, plugin.previous_note)
        prev_note_exits = True
    # [#NEXT] のノートを追加する
    if plugin.next_note is None:
        next_note_exists = False
    else:
        plugin.notes.append(plugin.next_note)
        next_note_exists = True
    print('len(plugin.notes)', len(plugin.notes))

    # Ust → HTSFullLabel
    full_label = convert_ustobj_to_htsfulllabelobj(plugin, table)
    # HTSFullLabel中の重複データを削除して整理
    full_label.generate_songobj()
    full_label.fill_contexts_from_songobj()

    print('len(full_label):', len(full_label))
    # [#PREV] のノート(の情報がある行)を削ると [#NEXT]
    if prev_note_exits:
        del full_label[0]
        while full_label[0].syllable.position != 1:
            del full_label[0]
    # [#NEXT] のノート(の情報がある行)を削ると [#NEXT]
    if next_note_exists:
        del full_label[-1]
        while full_label[-1].syllable.position_backward != 1:
            del full_label[-1]
    print('len(full_label):', len(full_label))

    # 整合性チェック
    if check:
        full_label.song.check()
    # ファイル出力
    full_label.write(path_hts, encoding='utf-8', strict_sinsy_style=strict_sinsy_style)


def main(path_plugin: str):
    """
    UtauPluginオブジェクトから音声ファイルを作る
    """
    # UTAUの一時ファイルに書いてある設定を読み取って捨てる
    plugin = up.utauplugin.load(path_plugin)
    str_now = datetime.now().strftime('%Y%m%d%h%M%S')
    path_ust, voice_dir, cache_dir = get_project_path(plugin)
    del plugin

    # 使用するモデルの設定
    enuconfig_name = 'enuconfig'
    # ドライブが違うとrelpathが使えないので、カレントディレクトリを変更する
    if splitdrive(voice_dir)[0] != splitdrive(getcwd())[0]:
        chdir(voice_dir)
    # configファイルを読み取る
    initialize(config_path=relpath(voice_dir))
    cfg = compose(config_name=enuconfig_name, overrides=[f'+config_path="{relpath(voice_dir)}"'])

    # 入出力パスを設定する
    path_lab = f'{cache_dir}/temp.lab'
    path_json = path_lab.replace('.lab', '.json')
    path_wav = f'{splitext(path_ust)[0]}__{str_now}.wav'
    # 変換テーブル(歌詞→音素)のパス
    path_table = f'{voice_dir}/{cfg.table_path}'
    # キャッシュフォルダがなければつくる
    makedirs(cache_dir, exist_ok=True)

    # ファイル処理
    strict_sinsy_style = not cfg.trained_for_enunu
    utauplugin2hts(path_plugin, path_lab, path_table, check=True, strict_sinsy_style=strict_sinsy_style)
    hts2json(path_lab, path_json)
    hts2wav(cfg, path_lab, path_wav)


if __name__ == '__main__':
    if len(argv) == 2:
        main(argv[1])
    elif len(argv) == 1:
        path_utauplugin = input('utauplugin temporary file path\n>>> ')
        main(path_utauplugin)
