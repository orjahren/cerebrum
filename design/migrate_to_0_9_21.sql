/*
 * Copyright 2019 University of Oslo, Norway
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
 */

/* SQL script for migrating a 0.9.20 database to 0.9.21 */

/*
 * The purpose of this migration is to add the group_moderator table to the
 * core tables
 */

category:pre;
CREATE TABLE group_moderator
(
  group_id     NUMERIC(12, 0)
               CONSTRAINT group_exists
               REFERENCES group_info(group_id),
  moderator_id NUMERIC(12, 0)
               CONSTRAINT moderator_exists
               REFERENCES entity_info(entity_id),
  CONSTRAINT group_moderator_pkey PRIMARY KEY (group_id, moderator_id)
);
