package axoloti.mcp;

import axoloti.MainFrame;
import axoloti.Preferences;
import axoloti.object.AxoObjects;
import axoloti.utils.OSDetect;
import org.junit.runner.JUnitCore;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;

/**
 * Test runner for GillsIntegrationTool tests.
 * This initializes the Axoloti environment first, then runs the tests.
 */
public class GillsIntegrationToolTestRunner {

    public static void main(String[] args) {
        try {
            // Initialize Axoloti environment
            initializeAxoloti();
            
            // Run the tests
            Result result = JUnitCore.runClasses(GillsIntegrationToolTest.class);
            
            // Print results
            System.out.println("\n--- TEST RESULTS ---");
            System.out.println("Tests run: " + result.getRunCount());
            System.out.println("Tests failed: " + result.getFailureCount());
            System.out.println("Tests ignored: " + result.getIgnoreCount());
            System.out.println("Time: " + result.getRunTime() + "ms");
            
            // Print failures
            if (!result.wasSuccessful()) {
                System.out.println("\n--- FAILURES ---");
                for (Failure failure : result.getFailures()) {
                    System.out.println(failure.toString());
                }
                System.exit(1);
            } else {
                System.out.println("\nAll tests passed successfully!");
            }
            
        } catch (Exception e) {
            System.err.println("Error initializing Axoloti environment:");
            e.printStackTrace();
            System.exit(1);
        }
    }
    
    /**
     * Initialize the Axoloti environment needed for tests.
     */
    private static void initializeAxoloti() throws Exception {
        System.out.println("Initializing Axoloti environment for tests...");
        
        // Initialize OS detection
        OSDetect.getOS();
        
        // Initialize preferences
        Preferences.LoadPreferences();
        
        // Initialize AxoObjects
        AxoObjects.loadAxoObjects();
        
        // Create MainFrame (needed for Axoloti object system)
        MainFrame.mainframe = new MainFrame();
        
        System.out.println("Axoloti environment initialized successfully.");
    }
} 