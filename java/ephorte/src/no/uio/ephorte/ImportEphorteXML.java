package no.uio.ephorte;

import java.io.FileInputStream;
import java.io.IOException;
import java.rmi.RemoteException;
import java.util.Enumeration;
import java.util.Hashtable;
import java.util.Properties;
import java.util.Vector;

import javax.xml.parsers.ParserConfigurationException;

import no.uio.ephorte.connection.EphorteGW;
import no.uio.ephorte.data.Person;
import no.uio.ephorte.xml.CustomXMLParser;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.xml.sax.SAXException;

public class ImportEphorteXML {
    private Log log = LogFactory.getLog(ImportEphorteXML.class);
    private EphorteGW ephorteGW;

    public ImportEphorteXML(EphorteGW ephorteGW) {
        this.ephorteGW = ephorteGW;
    }

    private static void usage() {
        System.out.println("Usage: import [options]\n"+
                "This script can be used to import data to ePhorte.\n\n"+
                "  -i fname : import specified filename\n"+
                "  -p fname : property filename (see example.props)\n"+
                "  -d table : dump table in a somewhat readable format\n"+
                "  -t tag   : tag to select from -d option"
                );
        System.exit(1);
    }

    /**
     * @param args
     * @throws ParserConfigurationException
     * @throws IOException
     * @throws SAXException
     */
    public static void main(String[] args) throws SAXException, IOException,
            ParserConfigurationException {
        String fname = null, table = null, tag = null;
	boolean testconn = false;
        Properties props = null;
        
        if(args.length < 2) usage();
        for (int i = 0; i < args.length; i++) {
            String cmd = args[i];
            if (cmd.equals("-c")) {
                testconn = true;
	    } else if(cmd.equals("-p")) {
                props = new Properties();
                props.load(new FileInputStream(args[++i]));
            } else if (cmd.equals("-i")) {
                fname = args[++i];
            } else if (cmd.equals("-d")) {
                table = args[++i];
            } else if (cmd.equals("-t")) {
                tag = args[++i];
            } else {
                usage();
            }
        }
        if(props == null) {
            System.err.println("-p required");
            System.exit(1);
        }
        ImportEphorteXML imp = new ImportEphorteXML(new EphorteGW(props));
        if(testconn) {
            System.out.println("Connection established. Look in log file for more details");
        } else if(table != null) {
            imp.dumpTable(table, tag);
        } else if (fname != null) {
            imp.runSync(fname);
        }
    }

    private void dumpTable(String table, String tag) throws RemoteException {
        // Example: -d pernavn -t PerNavn
        Vector<String> keys = new Vector<String>();
        Vector<Hashtable<String, String>> tmp = ephorteGW.getConn().getDataSet("object="+table, tag);
        for (Hashtable<String, String> ht : tmp) {
            for ( Enumeration<String> e = ht.keys(); e.hasMoreElements() ;) {
                String n = e.nextElement();
                if(! keys.contains(n)) {
                    keys.add(n);
                }
            }
        }                
        for (String k : keys) {
            System.out.print(k+";");
        }
        System.out.println();
        for (Hashtable<String, String> ht : tmp) {
            for (String k : keys) {
                System.out.print(ht.get(k)+";");
            }
            System.out.println();
        }
    }

    private void runSync(String fname) throws SAXException, IOException, ParserConfigurationException, RemoteException {
        ephorteGW.prepareSync();
        CustomXMLParser cp = new CustomXMLParser(fname);
        for (Person p : cp.getPersons()) {
            ephorteGW.updatePersonInfo(p);
        }
        log.info("All done");
    }
}
