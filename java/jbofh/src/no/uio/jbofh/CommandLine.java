/*
 * CommandLine.java
 *
 * Created on November 4, 2002, 11:06 AM
 */

package no.uio.jbofh;

import java.util.Vector;
import org.gnu.readline.*;
import java.io.EOFException;
import org.apache.log4j.Category;

/**
 *
 * @author  runefro
 */
public class CommandLine {
    Category logger;
    
    /** Creates a new instance of CommandLine */
    public CommandLine(Category logger) {
        Readline.initReadline("myapp");
        this.logger = logger;
        Runtime.getRuntime().addShutdownHook(new Thread() {
            public void run() {
                Readline.cleanup();
            }
        });
    }

    /**
     * @param str
     * @return An array consisting of commands separated by whitespace. Pairs of '/" signs will be grouped
     */    
    String [] splitCommand(String str) {
        /* This could probably be done easier by using String.parse(), but that would require JDK1.4 */
        
        char chars[] = (str+" ").toCharArray();
        Vector ret = new Vector();
        int i = 0, pstart = 0;
        Character quote = null;
        while(i < chars.length) {
            if(quote != null) {
                if(chars[i] == quote.charValue()) {                
                    if(i > pstart) 
                        ret.add(new String(str.substring(pstart, i)));
                    pstart = i+1;
                    quote = null;
                }                
            } else {
                if(chars[i] == '\'' || chars[i] == '"') {
                    pstart = i+1;
                    quote = new Character(chars[i]);
                } else if(chars[i] == ' ') {                
                    if(i > pstart) 
                        ret.add(new String(str.substring(pstart, i)));
                    pstart = i+1;
                }
            }
            i++;
        }
        String r[] = new String[ret.size()];
        for(i = 0; i < ret.size(); i++) r[i] = (String) ret.get(i);
        return r; // (String []) ret.toArray();
    }
    
    String [] getSplittedCommand() {
        while (true) {
            try {
                String line = Readline.readline("myprompt> ");
                if(line != null) 
                    return splitCommand(line);
            } catch (EOFException e) {
                return null;
            } catch (Exception e) {
                logger.error("Unexpected exception reading commandline", e);
                System.out.println("Unexpected error: "+e);
                String empty[] = {};
                return empty;
            }
        }
    }
}
