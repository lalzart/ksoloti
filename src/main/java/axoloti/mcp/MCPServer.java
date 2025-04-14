package axoloti.mcp;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.concurrent.Executors;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.json.JSONException;
import org.json.JSONObject;
import axoloti.PatchFrame;
import axoloti.PatchGUI;
import axoloti.MainFrame;

/**
 * HTTP Server implementation for Ksoloti MCP (Model-Controlled Programming)
 * Allows creating patches with natural language via HTTP requests
 */
public class MCPServer {
    private static final Logger LOGGER = Logger.getLogger(MCPServer.class.getName());
    
    private HttpServer server;
    private final int port;
    private boolean running = false;
    private final NLPPatchGenerator patchGenerator;
    
    public MCPServer(int port) {
        this.port = port;
        this.patchGenerator = new NLPPatchGenerator();
    }
    
    public void start() {
        if (running) {
            LOGGER.info("MCP Server is already running");
            return;
        }
        
        int attemptPort = port;
        final int MAX_PORT_ATTEMPTS = 10;
        boolean serverStarted = false;
        
        for (int attempt = 0; attempt < MAX_PORT_ATTEMPTS; attempt++) {
            try {
                server = HttpServer.create(new InetSocketAddress(attemptPort), 0);
                
                // Register endpoints
                server.createContext("/api/generate", new GeneratePatchHandler());
                server.createContext("/api/health", new HealthCheckHandler());
                
                // Set executor for request handling
                server.setExecutor(Executors.newFixedThreadPool(10));
                server.start();
                
                running = true;
                LOGGER.info("MCP Server started on port " + attemptPort);
                serverStarted = true;
                break;
            } catch (IOException e) {
                LOGGER.log(Level.WARNING, "Failed to start MCP server on port " + attemptPort + ", trying next port", e);
                // Try the next port
                attemptPort++;
            }
        }
        
        if (!serverStarted) {
            LOGGER.log(Level.SEVERE, "Failed to start MCP server after " + MAX_PORT_ATTEMPTS + " attempts");
        }
    }
    
    public void stop() {
        if (server != null && running) {
            server.stop(0);
            running = false;
            LOGGER.info("MCP Server stopped");
        }
    }
    
    public boolean isRunning() {
        return running;
    }
    
    /**
     * Handler for generating patches from natural language
     */
    class GeneratePatchHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            try {
                // Set CORS headers
                exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
                exchange.getResponseHeaders().add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                exchange.getResponseHeaders().add("Access-Control-Allow-Headers", "Content-Type,Authorization");
                
                if (exchange.getRequestMethod().equalsIgnoreCase("OPTIONS")) {
                    exchange.sendResponseHeaders(204, -1);
                    return;
                }
                
                if (!exchange.getRequestMethod().equalsIgnoreCase("POST")) {
                    sendResponse(exchange, 405, "{\"status\":\"error\",\"message\":\"Method Not Allowed. Please use POST.\"}");
                    return;
                }
                
                // Read request body
                java.util.Scanner s = new java.util.Scanner(exchange.getRequestBody()).useDelimiter("\\A");
                String requestBody = s.hasNext() ? s.next() : "";
                
                // Parse the request JSON
                JSONObject requestJson;
                String description;
                try {
                    requestJson = new JSONObject(requestBody);
                    description = requestJson.getString("description");
                } catch (JSONException e) {
                    sendResponse(exchange, 400, "{\"status\":\"error\",\"message\":\"Invalid request format. Expected JSON with 'description' field.\"}");
                    return;
                }
                
                // Generate the patch
                try {
                    // Generate patch in background thread to avoid blocking HTTP thread
                    java.util.concurrent.CompletableFuture.runAsync(() -> {
                        try {
                            final PatchGUI patch = patchGenerator.generatePatch(description);
                            
                            // UI updates must be on the EDT
                            javax.swing.SwingUtilities.invokeLater(() -> {
                                try {
                                    // Generate a filename
                                    String fileName = "generated_" + System.currentTimeMillis();
                                    
                                    // Create and initialize the patch frame FIRST
                                    PatchFrame pf = new PatchFrame(patch, MainFrame.mainframe.getQcmdprocessor());
                                    
                                    // Then set the filename (now that patch has a patchframe)
                                    patch.setFileNamePath(fileName);
                                    
                                    // Now call PostContructor after PatchFrame is created
                                    patch.PostContructor();
                                    
                                    // Finally show the patch frame
                                    pf.setVisible(true);
                                } catch (Exception e) {
                                    LOGGER.log(Level.SEVERE, "Error displaying generated patch", e);
                                }
                            });
                        } catch (Exception e) {
                            LOGGER.log(Level.SEVERE, "Error generating patch", e);
                        }
                    });
                    
                    // Respond immediately without waiting for patch generation
                    sendResponse(exchange, 202, "{\"status\":\"accepted\",\"message\":\"Patch generation started. The patch will open when ready.\"}");
                } catch (Exception e) {
                    LOGGER.log(Level.SEVERE, "Error processing patch generation", e);
                    sendResponse(exchange, 500, "{\"status\":\"error\",\"message\":\"Internal server error: " + e.getMessage() + "\"}");
                }
            } catch (Exception e) {
                LOGGER.log(Level.SEVERE, "Error handling request", e);
                sendResponse(exchange, 500, "{\"status\":\"error\",\"message\":\"Internal Server Error\"}");
            }
        }
    }
    
    /**
     * Handler for health checks
     */
    class HealthCheckHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            sendResponse(exchange, 200, "{\"status\":\"up\",\"version\":\"1.0.0\"}");
        }
    }
    
    /**
     * Helper method to send HTTP responses
     */
    private void sendResponse(HttpExchange exchange, int statusCode, String response) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        byte[] responseBytes = response.getBytes();
        exchange.sendResponseHeaders(statusCode, responseBytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(responseBytes);
        }
    }
} 