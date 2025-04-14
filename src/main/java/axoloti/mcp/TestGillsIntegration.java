package axoloti.mcp;

import axoloti.MainFrame;
import axoloti.object.AxoObjects;
import axoloti.PatchFrame;
import axoloti.PatchGUI;
import axoloti.utils.Preferences;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;

/**
 * Test class for demonstrating Gills integration with the NLP patch generator
 */
public class TestGillsIntegration {
    private static final Logger LOGGER = Logger.getLogger(TestGillsIntegration.class.getName());

    public static void main(String[] args) {
        try {
            // Initialize preferences and AxoObjects
            Preferences.LoadPreferences();
            MainFrame.axoObjects.LoadAxoObjects();
            
            // Create and show the test window
            SwingUtilities.invokeLater(() -> createAndShowGUI());
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error initializing Test Gills Integration", e);
        }
    }
    
    private static void createAndShowGUI() {
        try {
            // Create main frame
            JFrame frame = new JFrame("Gills Integration Test");
            frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
            frame.setSize(800, 600);
            
            // Create test patch with Gills controls
            PatchGUI patch = new PatchGUI();
            PatchFrame patchFrame = new PatchFrame(patch, null);
            patch.setFileNamePath("test_gills_integration.axp");
            patch.PostContructor();
            
            // Add Gills controls using our new integration tool
            String description = "A synthesizer with three oscillators, a filter, and an envelope, using Ksoloti Gills hardware for control. " +
                                "Use potentiometers for frequency and filter cutoff, buttons for triggering notes, and LEDs for indicating envelope state.";
            
            int controlsAdded = GillsIntegrationTool.addGillsControlsFromDescription(patch, description);
            LOGGER.info("Added " + controlsAdded + " Gills controls to the patch");
            
            // Show the frame with the patch
            frame.add(patchFrame);
            frame.setVisible(true);
            
            // Log a message to show the test is complete
            LOGGER.info("Gills Integration Test initialized successfully");
            
            // Create another example with auto-connections
            new Thread(() -> {
                try {
                    // Wait a moment before creating the second example
                    Thread.sleep(2000);
                    
                    // Use the NLPPatchGenerator to create a complete patch with Gills integration
                    SwingUtilities.invokeLater(() -> {
                        try {
                            PatchGUI autoConnectedPatch = new NLPPatchGenerator().generatePatch(
                                "Create a simple synthesizer with an oscillator, filter, and reverb. " +
                                "Use Ksoloti Gills hardware with potentiometers to control frequency, filter cutoff, and reverb amount. " +
                                "Add a button to trigger notes and an LED to show when notes are playing."
                            );
                            
                            if (autoConnectedPatch != null) {
                                PatchFrame autoConnectedFrame = new PatchFrame(autoConnectedPatch, null);
                                autoConnectedPatch.setFileNamePath("test_gills_auto_connected.axp");
                                autoConnectedPatch.PostContructor();
                                
                                JFrame frame2 = new JFrame("Gills Auto-Connected Example");
                                frame2.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE);
                                frame2.setSize(800, 600);
                                frame2.add(autoConnectedFrame);
                                frame2.setVisible(true);
                                
                                LOGGER.info("Auto-connected Gills patch created successfully");
                            } else {
                                LOGGER.warning("Failed to create auto-connected patch");
                            }
                        } catch (Exception e) {
                            LOGGER.log(Level.SEVERE, "Error creating auto-connected patch", e);
                        }
                    });
                } catch (Exception e) {
                    LOGGER.log(Level.SEVERE, "Error in example thread", e);
                }
            }).start();
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error creating GUI", e);
        }
    }
} 