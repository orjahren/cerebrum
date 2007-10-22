#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
"""This script created and syncs OU Groups for all OUs existing in Cerebrum"""



# ************************ General script execution explaination  *************************#

# Load dicts to speed up process

# Load ou corresponding to default_start_ou

# Call recursive function with loaded ou
   # if loaded ou does not have group, create group
   # else remove group_id from group_delete_list
   
   # if loaded ou has parent ou
      # if group corresponding to loaded ou is not member of group corresponding to parent ou, add membership
      # else remove member from members_delete_dict

   # for each affiliated person on loaded ou
      # if person and its affiliation does not exist on group corresponding to loaded ou, add membership
      # else remove member from members_delete_dict

   # for each child of loaded ou
      # run recursive function

# Remove non synced data
   # Remove all members remaining in members_delete_dict
   # Remove/Expire all empty ou-groups:*:TEKNISK/VITENSKAPELIG/STUDENT/EVT
   # Remove/Expire all groups remaining in group_delete_list


import cerebrum_path
import cereconf

import sys
import getopt
import mx

from Cerebrum.Utils import Factory
from Cerebrum.Constants import Constants
from Cerebrum import Entity
from Cerebrum.modules.no.Stedkode import Stedkode

logger = db = None
group_dict = members_dict = ou_affiliates_dict = group_description_dict = stedkode_dict = description_group_dict = {}
group_delete_list = members_delete_dict = None 

# Default values
default_perspective = 1
default_logger = 'cronjob'
default_prefix = 'ou_groups'
default_separator = ':'
default_start_ou = 3 # Universitetet i Tromsø
default_group_visibility = None
default_spread = None
default_creator = None
default_memberop = None
group_type_id = None
group_namespace = None
account_type_id = None

# Used to create container groups for account members
possible_member_types = ['VITENSKAPELIG','TEKNISK','STUDENT']
# Used to determine which aff_code_statuses correspond to which container group
member_type_mappings = {'VITENSKAPELIG': [222,197,211],
                        'TEKNISK':[210,],
                        'STUDENT':[215,212]}


db = Factory.get('Database')()
db.cl_init(change_program='process_ou_groups.py')

def process_ou_groups(ou, perspective):
    """Recursive function that will create groups and add spreads and members to them."""
    global logger, group_dict, members_dict, ou_affiliates_dict, stedkode_dict, \
           group_delete_list, members_delete_dict, \
           db, default_logger, default_group_visibility, default_creator, default_spread, \
           group_type_id, default_memberop, account_type_id, description_group_dict

    logger.info("Now processing OU %s (%s)" % (ou.ou_id, ou.name))

    gr = Factory.get('Group')(db)
    aux_gr = Factory.get('Group')(db)

    if not group_dict.has_key(ou.ou_id):
        logger.info("Create group and give spread")
        # create group and give spread
        gr_name = ou.name + ' (' + stedkode_dict[ou.ou_id] + ')'
        gr.new(creator=default_creator, visibility=default_group_visibility, \
               name = gr_name, \
               description='ou_group:'+stedkode_dict[ou.ou_id])
        gr.add_spread(default_spread)
        current_group = gr.entity_id
        group_dict[ou.ou_id] = current_group
        group_description_dict[current_group] = gr.description
        description_group_dict[gr.description] = current_group
    else:
        # remove from delete dict
        logger.info("Group already exists")
        current_group = group_dict[ou.ou_id]
        group_delete_list.remove(current_group)
   
    # if loaded ou has parent ou
    if ou.get_parent(perspective):
        logger.info("OU has parent - checking if group needs to be made member of parent group.")
        parent_group = group_dict[ou.get_parent(perspective)]
        
        # if group corresponding to loaded ou is not member of group corresponding to parent ou
        if not members_dict.has_key(parent_group):
            members_dict[parent_group] = []
        if not (current_group, None) in members_dict[parent_group]:
            # add group member
            logger.info("Add current group (%s) as member of parent group (%s)" % (current_group, parent_group))

            gr.clear()
            gr.find(parent_group)
            gr.add_member(current_group, group_type_id, default_memberop)
            
            members_dict[parent_group].append((current_group, None))
        else:
            # remove member from members_delete_dict
            logger.info("Current group already member of supposed parent group")
            members_delete_dict[parent_group].remove((current_group, None))
            

    # for each affiliated person on loaded ou
    if not ou_affiliates_dict.has_key(ou.ou_id):
        logger.info("No affiliates on current OU")
    else:
        logger.info("Cycling affiliates of current OU")
        for affiliate in ou_affiliates_dict[ou.ou_id]:
            # if person and its affiliation does not exist on group corresponding to loaded ou, add membership*
        
            if not members_dict.has_key(current_group):
                members_dict[current_group] = []
        
            if not affiliate in members_dict[current_group]:
                # add membership
                logger.info("Affiliate %s is not member - will be added as group member, type %s" %
                                                                    (affiliate[0], affiliate[1]))

                container_exists = False
                for aux_affiliate in members_dict[current_group]:
                    if aux_affiliate[1] == affiliate[1]:
                        container_exists = True
                        break

                # Create container group
                if not container_exists:
                    gr.clear()
                    gr_name = ou.name + ' (' + stedkode_dict[ou.ou_id] + ')' + ' - ' + affiliate[1]
                    gr.new(creator=default_creator, visibility=default_group_visibility, \
                           name=gr_name, \
                           description='ou_group:'+stedkode_dict[ou.ou_id]+':'+affiliate[1])
                    gr.add_spread(default_spread)
                    aux_gr.clear()
                    aux_gr.find(current_group)
                    aux_gr.add_member(gr.entity_id, group_type_id, default_memberop)
                    members_dict[current_group].append((gr.entity_id, None))
                else:
                    gr.clear()
                    gr.find(description_group_dict['ou_group:'+stedkode_dict[ou.ou_id]+':'+affiliate[1]])
                
                gr.add_member(affiliate[0], account_type_id, default_memberop)
                
                members_dict[current_group].append(affiliate)
                group_description_dict[gr.entity_id] = gr.description
                description_group_dict[gr.description] = gr.entity_id
            else:
                # remove member from members_delete_dict
                members_delete_dict[current_group].remove(affiliate)
    
    # for each child of loaded ou, run recursive function
    children = ou.list_children(perspective)
    for child in children:
        ou.clear()
        ou.find(long(child['ou_id']))
        process_ou_groups(ou, perspective)
            
    return


    
def clean_up_ou_groups():
    """Function that will remove obsolete groups and members"""
    global group_delete_list, members_delete_dict, group_description_dict, description_group_dict, \
           db, default_spread, group_namespace

    gr = Factory.get('Group')(db)

    # Remove all members remaining in members_delete_dict
    for group_id in members_delete_dict.keys():

        for member in members_delete_dict[group_id]:
            member_id = member[0]
            member_type = member[1]
            
            if member_type is None:
                working_group = group_id
            else:
                working_group = description_group_dict[group_description_dict[group_id]+':'+member_type]

            gr.clear()
            gr.find(working_group)
            logger.info("Removing old member %s from group %s" % (member_id, working_group))
            gr.remove_member(member_id, default_memberop)
    
    # Remove all empty ou-groups:*:TEKNISK/VITENSKAPELIG/STUDENT/EVT
    for member_type in possible_member_types:
        logger.info("Searching empty container groups for " + member_type)
        groups = gr.search(description = 'ou_group:%:'+member_type)
        for group in groups:
            gr.clear()
            gr.find(group[0])
            tmp = gr.list_members()[0]
            if len(tmp) == 0:
                obsolete_group = gr.entity_id
                obsolete_group_name = gr.get_name(group_namespace)
                logger.info("Expiring empty container group %s (%s)" %
                            (obsolete_group, obsolete_group_name))
                gr.expire_date = mx.DateTime.now()
                gr.write_db()
                logger.info("Prefixing its group_name with its group_id")
                gr.update_entity_name(group_namespace, '#' + str(obsolete_group) + '# ' + obsolete_group_name)
                old_parents = gr.list_groups_with_entity(obsolete_group)
                for old_parent in old_parents:
                    gr.clear()
                    gr.find(old_parent[0])
                    logger.info("Removing its membership from parent group %s (%s)" %
                                 (gr.entity_id, gr.get_name(group_namespace)))
                    gr.remove_member(obsolete_group, default_memberop)
                    gr.write_db()
             
    # Remove all groups remaining in group_delete_list
    for group_id in group_delete_list:
        gr.clear()
        gr.find(group_id)
        logger.info("Expiring unused OU group %s (%s)" % (group_id, gr.description))
        gr.expire_date = mx.DateTime.now()
        gr.write_db()
        logger.info("Prefixing its group_name with its group_id")        
        gr.update_entity_name(group_namespace, '#' + str(group_id) + '# ' + gr.get_name(group_namespace))
        
    return


def main():
    global logger, group_dict, members_dict, ou_affiliates_dict, \
           group_delete_list, members_delete_dict, stedkode_dict, \
           db, default_perspective, default_logger, default_start_ou, group_description_dict, \
           possible_member_types, member_type_mappings, default_creator, default_spread, \
           default_group_visibility, default_memberop, group_type_id, account_type_id, description_group_dict, \
           group_namespace

    logger = Factory.get_logger(default_logger)
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'pd',['perspective', 'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = 0
    perspective = default_perspective
    for opt,val in opts:
        if opt in('-p','--perspective'):
            perpective = val
        if opt in('-d','--dryrun'):
            dryrun = 1

    ou = Factory.get('OU')(db)
    gr = Factory.get('Group')(db)

    # Load default constant values
    co = Factory.get('Constants')(db)
    default_group_visibility = co.group_visibility_all
    default_spread = co.spread_uit_ad_group
    default_memberop = co.group_memberop_union
    group_type_id = co.entity_group
    account_type_id = co.entity_account
    group_namespace = co.group_namespace

    # Load group_dict - {ou_id:group_id}
    #      group_delete_list - [ou_id,]
    #      group_description_dict - {group_id:description}
    logger.info("Loading dict: ou > group_id")
    group_dict = {}
    group_description_dict = {}
    group_delete_list = []
    stedkoder = ou.get_stedkoder()
    groups = gr.search(description = 'ou_group:*')

    for stedkode in stedkoder:
        stedkode_dict[stedkode['ou_id']] = str(stedkode['fakultet']).zfill(2) + \
                                           str(stedkode['institutt']).zfill(2) + \
                                           str(stedkode['avdeling']).zfill(2)
    for group in groups:
        # Cache group description no matter what
        group_description_dict[group['group_id']] = group['description']
        description_group_dict[group['description']] = group['group_id']

        # Skip group caching if group is a container for account members
        skip = False
        for possible_type in possible_member_types:
            if group['description'].find(possible_type) > -1:
                skip = True
            break
        if skip == True:
            continue

        # OU groups are cached
        elems = group['description'].split(':')

        if len(elems)==2:
            group_delete_list.append(group['group_id'])


        # Only OU groups (and not containers) are cached!
        for stedkode in stedkoder:
                if len(elems)==2 and elems[1] == str(stedkode['fakultet']).zfill(2) + \
                               str(stedkode['institutt']).zfill(2) + \
                               str(stedkode['avdeling']).zfill(2):
                    group_dict[stedkode['ou_id']] = group['group_id']
                    break

    # Load members dict - {group_id:(member_id, member_type)}
    #  *** member_type is: GRUPPE, TEKNISK, VITENSKAPELIG, STUDENT, GJEST... ***
    logger.info("Loading dict: group_id > members")
    members_dict = {}
    members_delete_dict = {}
    aux_group = Factory.get('Group')(db)
    working_group = Factory.get('Group')(db)
    # NO NEED TO EXECUTE QUERY AGAIN: groups = gr.search(description = 'ou_group:*')
    for group in groups:

        # Skip member caching if group is a container for account members
        skip = False
        for possible_type in possible_member_types:
            if group['description'].find(possible_type) > -1:
                skip = True
                break
        if skip == True:
            continue
        
        working_group.clear()
        working_group.find(group['group_id'])
        members = working_group.list_members()[0]
            
        for member in members:
            # For each account member container, fill inn members for OU group
            member_is_ou = True
            ix_member_type = 0 # member tuple index for member type
            ix_member_id = 1 # member tuple index for member id

            for possible_type in possible_member_types:
                if member[ix_member_type] == group_type_id and \
                       group_description_dict[member[ix_member_id]] == \
                       group_description_dict[group['group_id']] + ':' + possible_type:

                    aux_group.clear()
                    aux_group.find(member[ix_member_id])
                    aux_members = aux_group.list_members()[0]
                    for aux_member in aux_members:
                        if aux_member[ix_member_type] == account_type_id:
                            if not members_dict.has_key(group['group_id']):
                                members_dict[group['group_id']] = []
                                members_delete_dict[group['group_id']] = []
                            members_dict[group['group_id']].append((aux_member[ix_member_id], possible_type))
                            members_delete_dict[group['group_id']].append((aux_member[ix_member_id], possible_type))
                    member_is_ou = False
                    break
                
            if member_is_ou:
                if not members_dict.has_key(group['group_id']):
                    members_dict[group['group_id']] = []
                    members_delete_dict[group['group_id']] = []
                members_dict[group['group_id']].append((member[ix_member_id], None))
                members_delete_dict[group['group_id']].append((member[ix_member_id], None))


    #159419L: [(159933L, None), (159938L, None)]

    # Load person to account dict (for local use)
    ac = Factory.get('Account')(db)
    primary_acs = ac.list_accounts_by_type(primary_only=True)
    person2acc = {}
    for primary_ac in primary_acs:
        person2acc[primary_ac['person_id']] = primary_ac['account_id']

    # Load creator id (global)
    ac.clear()
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator = ac.entity_id

    # Load ou affiliates dict - {ou_id:[(person_id, affiliation),]}
    logger.info("Loading dict: ou_id > affiliates")
    ou_affiliates_dict = {}

    pe = Factory.get('Person')(db)
    affs = pe.list_affiliations()
    for aff in affs:
        for possible_type in possible_member_types:
            if aff['status'] in member_type_mappings[possible_type]:
                tmp_acc_id = None
                if person2acc.has_key(aff['person_id']):
                    tmp_acc_id = person2acc[aff['person_id']]
                else:
                    logger.debug('Could not find primary account for person: %s' % (aff['person_id']))
                    break

                aff_tuple = (tmp_acc_id, possible_type)

                # Skip repeated entries and avoid creating entries for an OU until it has affiliates
                if not ou_affiliates_dict.has_key(aff['ou_id']) or not aff_tuple in ou_affiliates_dict[aff['ou_id']]:
                    if not ou_affiliates_dict.has_key(aff['ou_id']):
                        ou_affiliates_dict[aff['ou_id']] = []
                    ou_affiliates_dict[aff['ou_id']].append(aff_tuple)
                    continue

    # Get start OU from ou_structure tree
    ou.clear()
    ou.find(default_start_ou)

##     print "============="
##     print group_delete_list
##     print "============="
##     print members_delete_dict
##     print "============="

    # Enter recursive function to process groups
    logger.info("Starting to process groups, first out is: %s" % ou.name)
    process_ou_groups(ou = ou, perspective = perspective)
    logger.info("Finished processing groups")

##     print "============="
##     print group_delete_list
##     print "============="
##     print members_delete_dict
##     print "============="

    # Delete groups belonging to no longer imported OUs and removing old members
    logger.info("Starting to clean up the mess left behind (Please read: expiring and deleting obsolete elements)")
    clean_up_ou_groups()
    logger.info("Finished cleaning up")

    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rolling back changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")
    
    

def usage():
    print """
    usage:: python process_ou_groups.py 
    -p | --perspective : filter process on determined perspective code
    -d | --dryrun      : do not commit changes
    """
    sys.exit(1)



if __name__=='__main__':
    main()
