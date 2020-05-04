# jack.tag: name information (ID3 among others) stuff for
# jack - tag audio from a CD and encode it using 3rd party software
# Copyright (C) 1999-2003  Arne Zellentin <zarne@users.sf.net>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import sys
import locale
import re

import jack.functions
import jack.ripstuff
import jack.targets
import jack.helpers
import jack.freedb
import jack.utils
import jack.misc
import jack.m3u

from jack.init import pyogg
from jack.init import eyed3
from jack.init import flac
from jack.init import mp4
from jack.globals import *

track_names = None
locale_names = None
genretxt = None

a_artist = None
a_title = None
discnum = None


def _set_id3_tag(
        mp3file, version, encoding, a_title, t_name, track_num, t_artist,
        genre, year, comment, play_count):
    tag = eyed3.id3.Tag()
    tag.parse(mp3file)
    tag.album = a_title
    tag.title = t_name
    tag.track_num = track_num
    tag.artist = t_artist

    old_genre = tag.genre
    if genre != -1:
        tag.genre = genre
    elif old_genre == None:
        tag.genre = 255

    if year != -1:
        tag.release_date = year
    if comment:
        tag.comments.set(comment)
    tag.play_count = play_count

    tag.save(mp3file, version, encoding=encoding)


def tag(freedb_rename):
    global a_artist, a_title

    ext = jack.targets.targets[
        jack.helpers.helpers[cf['_encoder']]['target']]['file_extension']

    if cf['_vbr'] and not cf['_only_dae']:
        total_length = 0
        total_size = 0
        for i in jack.ripstuff.all_tracks_todo_sorted:
            total_length = total_length + i[LEN]
            total_size = total_size + jack.utils.filesize(i[NAME] + ext)

    if cf['_set_id3tag'] and not jack.targets.targets[jack.helpers.helpers[cf['_encoder']]['target']]['can_posttag']:
        cf['_set_id3tag'] = 0

    # maybe export?
    if jack.freedb.names_available:
        a_artist = track_names[0][0]  # unicode
        a_title = track_names[0][1]  # unicode

        r1 = re.compile(r'( \(disc[ ]*| \(side[ ]*| \(cd[^a-z0-9]*)([0-9]*|One|Two|A|B)([^a-z0-9])', re.IGNORECASE)
        mo = r1.search(a_title)
        discnum = None
        if mo != None:
            discnum = a_title[mo.start(2):mo.end(2)].lstrip("0")
            a_title = a_title[0:mo.start(1)]
            if discnum == "One" or discnum == "one" or discnum == "A":
                discnum = "1"
            elif discnum == "Two" or discnum == "two" or discnum == "B":
                discnum = "2"

    if cf['_set_id3tag'] or freedb_rename:
        jack.m3u.init()
        # use freedb year and genre data if available
        if cf['_id3_year'] == -1 and len(track_names[0]) >= 3:
            cf['_id3_year'] = track_names[0][2]
        if cf['_id3_genre'] == -1 and len(track_names[0]) == 4:
            cf['_id3_genre'] = track_names[0][3]

        print("Tagging", end=' ')
        for i in jack.ripstuff.all_tracks_todo_sorted:
            sys.stdout.write(".")
            sys.stdout.flush()
            mp3name = i[NAME] + ext
            wavname = i[NAME] + ".wav"
            if track_names[i[NUM]][0]:
                t_artist = track_names[i[NUM]][0]
            else:
                t_artist = a_artist
            t_name = track_names[i[NUM]][1]
            t_comm = ""
            if not cf['_only_dae'] and cf['_set_id3tag']:
                if len(t_name) > 30:
                    if t_name.find("(") != -1 and t_name.find(")") != -1:
                        # we only use the last comment
                        t_comm = t_name.split("(")[-1]
                        if t_comm[-1] == ")":
                            t_comm = t_comm[:-1]
                            if t_comm[-1] == " ":
                                t_comm = t_comm[:-1]
                            t_name2 = t_name.replace(" (" + t_comm + ") ", "")
                            t_name2 = t_name2.replace(" (" + t_comm + ")", "")
                            t_name2 = t_name2.replace("(" + t_comm + ") ", "")
                            t_name2 = t_name2.replace("(" + t_comm + ")", "")
                        else:
                            t_comm = ""
                if jack.helpers.helpers[cf['_encoder']]['target'] == "mp3":
                    if cf['_write_id3v2']:
                        _set_id3_tag(
                            mp3name, eyed3.id3.ID3_V2_4, 'utf-8', a_title,
                            t_name, (
                                i[NUM], len(jack.ripstuff.all_tracks_orig)),
                            t_artist, cf['_id3_genre'], cf['_id3_year'], None,
                            int(i[LEN] * 1000.0 / 75 + 0.5)
                        )
                    if cf['_write_id3v1']:
                        # encoding ??
                        _set_id3_tag(
                            mp3name, eyed3.id3.ID3_V1_1, 'latin1',
                            a_title, t_name,
                            (i[NUM], len(jack.ripstuff.all_tracks_orig)),
                            t_artist, cf['_id3_genre'], cf[
                                '_id3_year'], t_comm,
                            int(i[LEN] * 1000.0 / 75 + 0.5)
                        )
                elif jack.helpers.helpers[cf['_encoder']]['target'] == "flac":
                    if flac:
                        f = flac.FLAC(mp3name)
                        if f.vc is None:
                            f.add_vorbiscomment()
                        f.vc['ALBUM'] = a_title
                        f.vc['TRACKNUMBER'] = str(i[NUM])
                        f.vc['TRACKTOTAL'] = str(len(jack.ripstuff.all_tracks_orig))
                        f.vc['TITLE'] = t_name
                        f.vc['ARTIST'] = t_artist
                        if cf['_id3_genre'] != -1:
                            f.vc['GENRE'] = id3genres[cf['_id3_genre']]
                        if cf['_id3_year'] != -1:
                            f.vc['DATE'] = str(cf['_id3_year'])
                        if cf['_various']:
                            f.vc['COMPILATION'] = "1"
                        else:
                            if 'COMPILATION' in f.vc:
                                del f.vc['COMPILATION']
                        if discnum:
                            f.vc['DISCNUMBER'] = discnum
                        else:
                            if 'DISCNUMBER' in f.vc:
                                del f.vc['DISCNUMBER']
                            if 'DISCTOTAL' in f.vc:
                                del f.vc['DISCTOTAL']
                        f.save()
                    else:
                        print()
                        print("Please install the Mutagen module available at")
                        print("https://mutagen.readthedocs.io/")
                elif jack.helpers.helpers[cf['_encoder']]['target'] == "m4a":
                    if mp4:
                        m4a = mp4.MP4(mp3name)
                        m4a.tags['\xa9nam'] = [t_name]
                        m4a.tags['\xa9alb'] = [a_title]
                        m4a.tags['\xa9ART'] = [t_artist]
                        if cf['_id3_genre'] != -1:
                            m4a.tags['\xa9gen'] = [id3genres[cf['_id3_genre']]]
                        if cf['_id3_year'] != -1:
                            m4a.tags['\xa9day'] = [str(cf['_id3_year'])]
                        m4a.tags['cpil'] = bool(cf['_various'])
                        m4a.tags['trkn'] = [(i[NUM], len(jack.ripstuff.all_tracks_orig))]
                        if discnum:
                            m4a.tags['disk'] = [(discnum, 0)]
                        m4a.save()
                    else:
                        print()
                        print("Please install the Mutagen module available at")
                        print("https://mutagen.readthedocs.io/")
                        print("Without it, you'll not be able to tag AAC tracks.")
                elif jack.helpers.helpers[cf['_encoder']]['target'] == "ogg":
                    vf = pyogg.VorbisFile(mp3name)
                    oggi = vf.comment()
                    oggi.clear()
                    oggi.add_tag('ALBUM', a_title)
                    oggi.add_tag('TRACKNUMBER', repr(i[NUM]))
                    oggi.add_tag('TITLE', t_name)
                    oggi.add_tag('ARTIST', t_artist)
                    if cf['_id3_genre'] != -1:
                        oggi.add_tag('GENRE', id3genres[cf['_id3_genre']])
                    if cf['_id3_year'] != -1:
                        oggi.add_tag('DATE', repr(cf['_id3_year']))
                    oggi.write_to(mp3name)
            if freedb_rename:
                newname = jack.freedb.filenames[i[NUM]]
                if i[NAME] != newname:
                    p_newname = newname
                    u_newname = newname
                    newname = newname
                    p_mp3name = i[NAME]
                    p_wavname = i[NAME]
                    ok = 1
                    if os.path.exists(newname + ext):
                        ok = 0
                        print('NOT renaming "' + p_mp3name + '" to "' + p_newname + ext + '" because dest. exists.')
                        if cf['_keep_wavs']:
                            print('NOT renaming "' + p_wavname + '" to "' + p_newname + ".wav" + '" because dest. exists.')
                    elif cf['_keep_wavs'] and os.path.exists(newname + ".wav"):
                        ok = 0
                        print('NOT renaming "' + p_wavname + '" to "' + p_newname + ".wav" + '" because dest. exists.')
                        print('NOT renaming "' + p_mp3name + '" to "' + p_newname + ext + '" because WAV dest. exists.')
                    if ok:
                        if not cf['_only_dae']:
                            try:
                                os.rename(mp3name, newname + ext)
                            except OSError:
                                error('Cannot rename "%s" to "%s" (Filename is too long or has unusable characters)' %
                                      (p_mp3name, p_newname + ext))
                            jack.m3u.add(newname + ext)
                        if cf['_keep_wavs']:
                            os.rename(wavname, newname + ".wav")
                            jack.m3u.add_wav(newname + ".wav")
                        jack.functions.progress(
                            i[NUM], "ren", "%s-->%s" % (i[NAME], u_newname))
                    elif cf['_silent_mode']:
                        jack.functions.progress(
                            i[NUM], "err", "while renaming track")
        print()

    if not cf['_silent_mode']:
        if jack.freedb.names_available:
            print("Done with \"" + a_artist + " - " + a_title + "\".")
        else:
            print("All done.", end=' ')
        if cf['_set_id3tag'] and cf['_id3_year'] != -1:
            print("Year: %4i" % cf['_id3_year'], end=' ')
            if cf['_id3_genre'] == -1:
                print()
        if cf['_set_id3tag'] and cf['_id3_genre'] != -1:
            if cf['_id3_genre'] < 0 or cf['_id3_genre'] > len(id3genres):
                print("Genre: [unknown]")
            else:
                print("Genre: %s" % id3genres[cf['_id3_genre']])
        if cf['_vbr'] and not cf['_only_dae']:
            print("Avg. bitrate: %03.0fkbit" % ((total_size * 0.008) / (total_length / 75)))
        else:
            print()

    if jack.m3u.m3u:
        os.environ["JACK_JUST_ENCODED"] = "\n".join(jack.m3u.m3u)
    if jack.m3u.wavm3u:
        os.environ["JACK_JUST_RIPPED"] = "\n".join(jack.m3u.wavm3u)
    jack.m3u.write()
