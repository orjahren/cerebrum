/* encoding: utf-8
 *
 * Copyright 2004-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.Email
 *
 * This file is a UiO specific Cerebrum extension.
 *
 * The tables herein model the information from the UiO's HR system - LT.
 * The data structure is described in mod_lt.dia.
 */
category:metainfo;
name=lt;

category:metainfo;
version=1.0;


category:drop;
drop TABLE lt_permisjon;
category:drop;
drop TABLE lt_reservasjon;
category:drop;
drop table lt_rolle;
category:drop;
drop table lt_gjest;
category:drop;
drop table lt_bilag;
category:drop;
drop table lt_tilsetting;
category:drop;
drop TABLE lt_permisjonskode;
category:drop;
drop table lt_rollekode;
category:drop;
drop table lt_gjestetypekode;
category:drop;
drop table lt_stillingskode;
category:drop;
drop table lt_lonnsstatus;


/* First, we create all code tables */

/*  lt_lonnsstatus
 *
 * codes describing various payment (lønn) categories
 */
category:code;
CREATE TABLE lt_lonnsstatus
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_lonnsstatus_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT lt_lonnsstatus_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*  lt_stillingskode
 *
 * codes describing various employments (stillinger)
 */
category:code;
CREATE TABLE lt_stillingskode
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_stillingskode_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT lt_stillingskode_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL,

  hovedkategori
    CHAR VARYING(3)
    NOT NULL,

  tittel
    CHAR VARYING(40)
    NOT NULL
);


/*  lt_gjestetypekode
 *
 * codes describing guests at UiO
 */
category:code;
CREATE TABLE lt_gjestetypekode
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_gjestetypekode_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT lt_gjestetypekode_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL,

  /* FIXME: what should this one be? */
  tittel
    CHAR VARYING(10)
    NOT NULL
);


/*  lt_rollekode
 *
 * codes describing various roles for people in Cerebrum
 */
category:code;
CREATE TABLE lt_rollekode
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_rollekode_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT lt_rollekode_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*  lt_permisjonskode
 *
 * codes describing various leaves of duty
 */
category:code;
CREATE TABLE lt_permisjonskode 
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_permisjonskode_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT lt_permisjonskode_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/* And now all the interesting tables */

/*  lt_tilsetting
 *
 * employment records
 */
category:main;
CREATE TABLE lt_tilsetting
(
  tilsettings_id
    NUMERIC(6,0)
    NOT NULL,

  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_tilsetting_person_id
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_tilsetting_ou_id
      REFERENCES stedkode(ou_id),

  stillingskode
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_tilsetting_stillingskode
      REFERENCES lt_stillingskode(code),

  dato_fra
    DATE
    NOT NULL,

  /* FIXME: What does NULL mean here? */
  dato_til
    DATE,

  /* Employment percentage -- [0,100] */
  andel
    NUMERIC(3,0)
    NOT NULL,

  CONSTRAINT lt_tilsetting_pk PRIMARY KEY (tilsettings_id, person_id)
);

category:main;
CREATE INDEX lt_tilsetting_person_id_index ON lt_tilsetting(person_id) ;


/* lt_bilag
 *
 * information about temporary employments
 */
category:main;
CREATE TABLE lt_bilag
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_bilag_person_id
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_bilag_ou_id
      REFERENCES stedkode(ou_id),

  dato
    DATE
    NOT NULL,

  CONSTRAINT lt_bilag_pk PRIMARY KEY (person_id, ou_id)
);

category:main;
CREATE INDEX lt_bilag_person_id_index ON lt_bilag(person_id) ;


/*  lt_gjest
 *
 * information about guests at UiO
 */
category:main;
CREATE TABLE lt_gjest
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_gjest_person_id
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_gjest_ou_id
      REFERENCES stedkode(ou_id),

  dato_fra
    DATE
    NOT NULL,

  gjestetypekode
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_gjest_gjestetypekode
      REFERENCES lt_gjestetypekode(code),

  /* FIXME: What does NULL mean here? */
  dato_til
    DATE,

  CONSTRAINT lt_gjest_pk PRIMARY KEY (person_id, ou_id, dato_fra)
);

category:main;
CREATE INDEX lt_gjest_person_id_index ON lt_gjest(person_id) ;


/*  lt_rolle
 *
 * information about roles played by various people
 */
category:main;
CREATE TABLE lt_rolle
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_rolle_person_id
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_rolle_ou_id
      REFERENCES stedkode(ou_id),

  rollekode
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_rolle_rollekode
      REFERENCES lt_rollekode(code),

  dato_fra
    DATE
    NOT NULL,

  /* FIXME: What does NULL mean here? */
  dato_til
    DATE,

  CONSTRAINT lt_rolle_pk PRIMARY KEY (person_id, ou_id, rollekode)
);

category:main;
CREATE INDEX lt_rolle_person_id_index ON lt_rolle(person_id) ;


/* lt_reservasjon
 *
 * information about reservations against catalogue publishing
 */
category:main;
CREATE TABLE lt_reservasjon
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT lt_reservasjon_person_id
      REFERENCES person_info(person_id)
    CONSTRAINT lt_reservasjon_pk PRIMARY KEY,

  reservert
    CHAR(1)
    NOT NULL
    CONSTRAINT lt_reservasjon_reservert_bool
      CHECK (reservert IN ('T', 'F'))
);

category:main;
CREATE INDEX lt_reservasjon_person_id_index ON lt_reservasjon(person_id) ;


/*  lt_permisjon
 *
 * information about leaves of absence
 */
category:main;
CREATE TABLE lt_permisjon
(
  tilsettings_id
    NUMERIC(6,0)
    NOT NULL,

  person_id
    NUMERIC(12,0)
    NOT NULL,

  permisjonskode
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_permisjon_permisjonskode
      REFERENCES lt_permisjonskode(code),

  dato_fra
    DATE
    NOT NULL,

  dato_til
    DATE
    NOT NULL,

  lonstatuskode
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT lt_permisjon_lonstatuskode
      REFERENCES lt_lonnsstatus(code),

  /* FIXME: Why does LT have such a strange type? This is still a
     percentage value */
  andel
    NUMERIC(8,2)
    NOT NULL,

  CONSTRAINT lt_permisjon_pk
    PRIMARY KEY (tilsettings_id, person_id, permisjonskode,
                 dato_fra, dato_til, lonstatuskode),

  CONSTRAINT lt_permisjon_tilsetting_fk
    FOREIGN KEY (tilsettings_id, person_id)
    REFERENCES lt_tilsetting(tilsettings_id, person_id)
);

category:main;
CREATE INDEX lt_permisjon_person_id_index
  ON lt_permisjon(person_id);

category:main;
CREATE INDEX lt_permisjon_person_tilsetting_index
  ON lt_permisjon(tilsettings_id, person_id);
