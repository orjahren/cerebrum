/* encoding: utf-8
 *
 * Copyright 2011-2019 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 *
 *
 * Tables used by ???
 */
category:metainfo;
name=bewidseq;

category:metainfo;
version=1.0;


category:drop;
drop SEQUENCE bewatorid_ans_seq;

category:drop;
drop SEQUENCE bewatorid_extstud_seq;


category:code;
CREATE SEQUENCE bewatorid_ans_seq
    INCREMENT BY 1
    MINVALUE 210001
    MAXVALUE 219999
    NO CYCLE;


category:code;
CREATE SEQUENCE bewatorid_extstud_seq
    INCREMENT BY 1
    MINVALUE 700000
    MAXVALUE 799999
    NO CYCLE;
