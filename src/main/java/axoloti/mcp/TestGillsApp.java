package axoloti.mcp;

import axoloti.MainFrame;
import axoloti.PatchGUI;
import axoloti.Preferences;
import axoloti.object.AxoObjects;
import axoloti.utils.OSDetect;
import axoloti.connection.IAxoConnection;
import axoloti.connection.CConnection;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.io.File;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Simple application to test the GillsIntegrationTool functionality.
 */
public class TestGillsApp {
    private static final Logger LOGGER = Logger.getLogger(TestGillsApp.class.getName());
    
    private JFrame frame;
    private JTextField descriptionField;
    private JTextArea resultArea;
    private PatchGUI patch;
    private JButton connectButton;
    private JButton uploadButton;
    
    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try {
                // Initialize Axoloti preferences and objects
                initializeAxoloti();
                
                // Create and show the app
                TestGillsApp app = new TestGillsApp();
                app.createAndShowGUI();
            } catch (Exception e) {
                LOGGER.log(Level.SEVERE, "Error starting application", e);
                JOptionPane.showMessageDialog(null, 
                        "Error starting application: " + e.getMessage(), 
                        "Error", JOptionPane.ERROR_MESSAGE);
                System.exit(1);
            }
        });
    }
    
    /**
     * Initialize Axoloti preferences and objects.
     */
    private static void initializeAxoloti() throws Exception {
        // Initialize OS detection and preferences
        OSDetect.getOS();
        
        // Set expert mode before loading preferences
        Preferences prefs = Preferences.LoadPreferences();
        prefs.setExpertMode(true);
        prefs.SavePrefs();
        
        LOGGER.info("Expert mode enabled: " + prefs.getExpertMode());
        
        // Ensure firmware directory exists
        String firmwarePath = prefs.getFirmwarePath();
        File firmwareDir = new File(firmwarePath);
        if (!firmwareDir.exists()) {
            LOGGER.warning("Firmware directory not found: " + firmwarePath);
        } else {
            LOGGER.info("Firmware directory: " + firmwarePath);
            // Check for firmware binary
            File firmwareBin = new File(firmwareDir, "build/ksoloti.bin");
            if (!firmwareBin.exists()) {
                LOGGER.warning("Firmware binary not found: " + firmwareBin.getAbsolutePath() + 
                               ". You may need to compile firmware first.");
            } else {
                LOGGER.info("Firmware binary found: " + firmwareBin.getAbsolutePath());
            }
        }
        
        // Initialize AxoObjects
        AxoObjects.loadAxoObjects();
        
        // Create MainFrame (needed for Axoloti object system)
        MainFrame.mainframe = new MainFrame();
    }
    
    /**
     * Create and show the GUI.
     */
    public void createAndShowGUI() {
        frame = new JFrame("Gills Integration Tool Test");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(800, 600);
        
        // Create components
        JPanel topPanel = new JPanel(new BorderLayout());
        descriptionField = new JTextField();
        JButton addButton = new JButton("Add Gills Controls");
        topPanel.add(new JLabel("Enter description: "), BorderLayout.WEST);
        topPanel.add(descriptionField, BorderLayout.CENTER);
        topPanel.add(addButton, BorderLayout.EAST);
        
        // Add connection management panel
        JPanel connectionPanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
        connectButton = new JButton("Connect to Device");
        uploadButton = new JButton("Upload to Device");
        connectionPanel.add(connectButton);
        connectionPanel.add(uploadButton);
        
        resultArea = new JTextArea();
        resultArea.setEditable(false);
        
        // Create an empty patch
        patch = new PatchGUI();
        JScrollPane patchView = new JScrollPane(patch);
        
        // Set up layout
        JSplitPane splitPane = new JSplitPane(
                JSplitPane.VERTICAL_SPLIT,
                new JScrollPane(resultArea),
                patchView);
        splitPane.setDividerLocation(150);
        
        JPanel mainPanel = new JPanel(new BorderLayout());
        mainPanel.add(connectionPanel, BorderLayout.NORTH);
        mainPanel.add(splitPane, BorderLayout.CENTER);
        
        frame.getContentPane().add(topPanel, BorderLayout.NORTH);
        frame.getContentPane().add(mainPanel, BorderLayout.CENTER);
        
        // Add action listeners
        addButton.addActionListener(this::processDescription);
        connectButton.addActionListener(e -> connectToDevice());
        uploadButton.addActionListener(e -> uploadToDevice());
        
        // Show the frame
        frame.setLocationRelativeTo(null);
        frame.setVisible(true);
        
        // Log startup info
        logInitialInfo();
    }
    
    /**
     * Process the description and add Gills controls.
     */
    private void processDescription(ActionEvent e) {
        String description = descriptionField.getText().trim();
        if (description.isEmpty()) {
            JOptionPane.showMessageDialog(frame, 
                    "Please enter a description", 
                    "Error", JOptionPane.ERROR_MESSAGE);
            return;
        }
        
        resultArea.append("Processing description: " + description + "\n");
        
        try {
            // Use GillsIntegrationTool to add controls
            int count = GillsIntegrationTool.addGillsControlsFromDescription(patch, description);
            
            resultArea.append("Added " + count + " Gills controls to the patch.\n");
            if (count == 0) {
                resultArea.append("No controls identified in the description. Try using more specific terms like 'pot for volume' or 'button for trigger'.\n");
            }
            
            // Force repaint to show the added controls
            patch.repaint();
            
        } catch (Exception ex) {
            LOGGER.log(Level.SEVERE, "Error processing description", ex);
            resultArea.append("Error: " + ex.getMessage() + "\n");
        }
    }
    
    /**
     * Connect to the Axoloti device.
     */
    private void connectToDevice() {
        try {
            resultArea.append("Attempting to connect to device...\n");
            
            // Get the current connection or create a new one
            IAxoConnection connection = MainFrame.mainframe.getConnection();
            if (connection == null) {
                connection = new CConnection();
                MainFrame.mainframe.setConnection(connection);
            }
            
            // Connect if not already connected
            if (!connection.isConnected()) {
                connection.disconnect();
                connection.connect();
                
                if (connection.isConnected()) {
                    resultArea.append("Successfully connected to device.\n");
                    connectButton.setText("Disconnect");
                } else {
                    resultArea.append("Failed to connect to device. Check connections and try again.\n");
                }
            } else {
                // If already connected, disconnect
                connection.disconnect();
                resultArea.append("Disconnected from device.\n");
                connectButton.setText("Connect to Device");
            }
        } catch (Exception ex) {
            LOGGER.log(Level.SEVERE, "Error connecting to device", ex);
            resultArea.append("Error connecting to device: " + ex.getMessage() + "\n");
        }
    }
    
    /**
     * Upload the current patch to the connected device.
     */
    private void uploadToDevice() {
        try {
            IAxoConnection connection = MainFrame.mainframe.getConnection();
            if (connection == null || !connection.isConnected()) {
                resultArea.append("Not connected to device. Please connect first.\n");
                return;
            }
            
            resultArea.append("Uploading patch to device...\n");
            
            // Transmit the patch to the device
            patch.uploadToDevice();
            
            resultArea.append("Patch uploaded successfully.\n");
        } catch (Exception ex) {
            LOGGER.log(Level.SEVERE, "Error uploading to device", ex);
            resultArea.append("Error uploading to device: " + ex.getMessage() + "\n");
        }
    }
    
    /**
     * Log initial application information.
     */
    private void logInitialInfo() {
        resultArea.setText("");
        resultArea.append("Gills Integration Tool Test Application\n");
        resultArea.append("----------------------------------------\n");
        resultArea.append("Enter a description of the controls you want to add in the field above.\n");
        resultArea.append("Examples:\n");
        resultArea.append("  - 'I need a pot for volume and another for frequency'\n");
        resultArea.append("  - 'Add a button for trigger and an LED for status'\n");
        resultArea.append("  - 'Create a volume knob and a cutoff slider'\n");
        resultArea.append("----------------------------------------\n");
        resultArea.append("CONNECTION: Please connect to the device first, then upload your patch.\n");
        resultArea.append("If connection fails, you may need to compile firmware first:\n");
        resultArea.append("  1. Open Terminal and navigate to firmware directory\n");
        resultArea.append("  2. Run 'make -j4' to build firmware\n");
        resultArea.append("  3. Try connecting again\n");
        resultArea.append("----------------------------------------\n");
    }
} 