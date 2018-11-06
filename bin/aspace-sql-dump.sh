#!/bin/bash

#######################################################################
# 2018-07-17 Tim DiLauro
# Dump ArchivesSpace database using ArchivesSpace configuration
#######################################################################

TARGET_DBNAME=archivesspace
CONFIG_FILE=/usr/share/archivesspace/config/config.rb
dumpfile=aspace-prod-$(date +'%Y%m%dT%H%M%S').dump.sql


#######################################################################
# NO CHANGES BELOW THIS LINE
#######################################################################

command_name=$(basename $0)

function print_usage {
  echo "-- HELP --------------------------------"
  echo "Usage: ${command_name} [-t <target-db>] [-f <config-file>] [-d <dumpfile>] [-u <db-user>] [-p[<db-pw>]] [-h <db-host>] [-P <db-port>]"
  echo
  echo "Text in angle brackets ('<>') should be replaced by a value."
  echo "Options or parameters in square brackets ('[]') are optional."
  echo "* Note: No space between -p and its optional password value, if provided."
  echo
  echo "Default ArchivesSpace target database name: '${TARGET_DBNAME}'"
  echo "Default ArchivesSpace configuration file name: '${CONFIG_FILE}'"
  echo "Default database dump SQL file name: '${dumpfile}'"
  echo "-- HELP --------------------------------"
}

function get_help {
  >&2 echo "Use '${command_name} --help' for help/usage."
  exit 1
}

# --help
# t: target db name (TARGET_DBNAME)
# f: config file name (config_file)
# P: override port number (DBPORT)
# u: override username
# h: override host
# o: override default output dump filename (dumpfile)
# n: dry-run - don't actually run the backup

# read the options -- need GNU getopts on MacOS
GNUPATH=/usr/local/opt/gnu-getopt/bin
if [ -d "${GNUPATH}" ]; then
    GETOPT="${GNUPATH}/getopt"
else
    GETOPT=getopt
fi
OPTIONS=$("${GETOPT}" -o 'f:t:d:h:P:u:p::o:n' --long 'help,config:,file:,target:,db:,database:host:,port:,user:,password::,dumpfile:,dry-run' -n "${command_name}" -- "$@")
eval set -- "${OPTIONS}"


# get opts and their arguments
while true; do
  case "$1" in
    -f|--config|--file) CONFIG_FILE=$2 ; shift 2 ;;
    -t|--target) TARGET_DBNAME=$2 ; shift 2 ;;
    -d|--db|--database) opt_dbname=$2 ; shift 2 ;;
    -h|--host) opt_dbhost=$2 ; shift 2 ;;
    -P|--port) opt_dbport=$2 ; shift 2 ;;
    -u|--user) if [ -n "${2+x}" ] ; then opt_dbuser=$2 ; fi ; shift 2 ;;
    -p|--password) opt_dbpass=$2 ; shift 2 ;;
    --help) print_usage ; exit ;;
    -o|--dumpfile) if [ "${2}" == '-' ] ; then dumpfile="/dev/stdout" ; else dumpfile="${2}" ; fi ; shift 2 ;;
    -n|--dry-run) DRY_RUN=1; shift ;;
    --) shift ; break ;;
    *) >&2 echo "Error parsing command line option ($1)" ; exit 1 ;;
  esac
done



get_db_name ()
{
   echo "$1" | sed -e "s|.*/\([^/?]*\)\?.*|\1|"
}


get_param ()
{
   echo "$1" | sed -e "s/.*[?&]${2}=\([^?&]*\).*/\1/"
}

get_host_port ()
{
    IFS=: read host port < <(echo "$1" | sed -e 's|.*//\([^/]*\).*|\1|')
    if [ -z "${port}" ]; then
        port = "3306"
    fi
    echo "${host} ${port}"
}


if [ -n "${CONFIG_FILE}" ] ; then
    if [ -f "${CONFIG_FILE}" ] ; then
        if [ -r "${CONFIG_FILE}" ] ; then
            url=$(grep '^ *AppConfig *\[ *:db_url *\] *=' ${CONFIG_FILE} | sed -e "s/.*= *[\'\"]\(.*\)[\'\"] */\1/")

            DBNAME=$(get_db_name "${url}")
            DBUSER=$(get_param "${url}" 'user')
            DBPASS=$(get_param "${url}" 'password')
            read DBHOST DBPORT < <(get_host_port "${url}")
        else
            >&2 echo "Specified configuration file is not readable: '${CONFIG_FILE}'"
            exit 1
        fi
    else
        >&2 echo "Specified configuration file must exist as a file: '${CONFIG_FILE}'"
        exit 1
    fi
fi

if [ -n "${opt_dbname+x}" ] ; then DBNAME="${opt_dbname}" ; fi
if [ -n "${opt_dbuser+x}" ] ; then DBUSER="${opt_dbuser}" ; fi
if [ -n "${opt_dbpass+x}" ] ; then
    if [ -n "${opt_dbpass}" ] ; then MYSQL_PWD="${opt_dbpass}"; export MYSQL_PWD ; fi
elif [ -n "${DBPASS+x}" ] ; then
    MYSQL_PWD="${DBPASS}"; export MYSQL_PWD
fi
if [ -n "${opt_dbhost+x}" ] ; then DBHOST="${opt_dbhost}" ; fi
if [ -n "${opt_dbport+x}" ] ; then DBPORT="${opt_dbport}" ; fi



if [ -n "${DRY_RUN+x}" ] ; then
    echo "Dry run -- the equivalent of the following command would have been executed:"
    echo """mysqldump -h "${DBHOST}" --port "${DBPORT}" -u "${DBUSER}" --databases "${DBNAME}" | sed -e "s/\`${DBNAME}\`/\`${TARGET_DBNAME}\`/g" > "${dumpfile}" """
    if [ -n "${MYSQL_PWD+x}" ] ; then echo "password is set"
    else echo "password is not set"
    fi
else
    if [ -z "${MYSQL_PWD+x}" ] ; then
        echo -n "Connecting to database server: "
        pwd_opt='-p'
    fi
    mysqldump -h "${DBHOST}" --port "${DBPORT}" ${pwd_opt} -u "${DBUSER}" --databases "${DBNAME}" \
    | sed -e "s/\`${DBNAME}\`/\`${TARGET_DBNAME}\`/g" > "${dumpfile}"
fi
