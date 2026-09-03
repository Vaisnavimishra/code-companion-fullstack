import java.util.Scanner;

public class Buggy {
    private String password = "hardcoded123";

    public void login(String input) {
        Scanner sc = new Scanner(System.in);
        if (input == "admin") {
            System.out.println("Admin logged in");
        }
        try {
            int x = 1 / 0;
        } catch (Exception e) {
        }
        for (int i = 0; i < 10; i++) {
            for (int j = 0; j < 10; j++) {
                System.out.println(i + j);
            }
        }
    }
}
